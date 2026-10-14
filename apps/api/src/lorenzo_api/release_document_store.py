"""Writing and reading a release's document - ADR 0214, RFC 0037 §4.

`store_release_document` writes the document of one release and the files it refers to,
from the `Content` the caller loaded (the same one the digest of the release is made from, so
the two cannot disagree). `read_release_content` reads them back as a `Content`, which is all
the update engine and the copy planner take.

Like `load_content`, both filter on the repository's id explicitly (ADR 0002): a member of the
repository reads and writes its own, a library reads inside `reading_repository` (ADR 0118).
A publish of a public repository writes one (ADR 0286); a private repository keeps none.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api import release_document
from lorenzo_api.models import RepositoryRelease, RepositoryReleaseBlob, RepositoryReleaseDocument
from lorenzo_api.release_document import ReleaseDocumentCorruptError, ReleaseDocumentError
from lorenzo_api.repository_content import Content

# Files go in a statement at a time, a few hundred of them, so none is too large to prepare.
_BATCH = 200


class ReleaseNotFoundError(ReleaseDocumentError):
    """The release is not one of this repository's."""


class ReleaseDocumentExistsError(ReleaseDocumentError):
    """A release has one document and it is never replaced."""


class ReleaseDocumentNotFoundError(ReleaseDocumentError):
    """No document of this release, or none this reader may see."""


@dataclass(frozen=True)
class StoredDocument:
    release_id: uuid.UUID
    format: int
    # What the document takes in the table: its gzipped bytes.
    size: int
    # The files it refers to, and how many of them were not stored yet.
    files: int
    new_files: int


async def store_release_document(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    release_id: uuid.UUID,
    content: Content,
) -> StoredDocument:
    """Writes the document of `release_id`, a release of the repository `tenant_id`, from
    `content`, and the files it refers to that the repository does not hold yet. Flushes, does
    not commit. A second document for a release is refused, and so is a content that is
    another tenant's."""
    if content.tenant_id != tenant_id:
        raise ReleaseDocumentError(f"the content is of {content.tenant_id}, not of {tenant_id}")
    release = await session.scalar(
        select(RepositoryRelease.id).where(
            RepositoryRelease.id == release_id, RepositoryRelease.tenant_id == tenant_id
        )
    )
    if release is None:
        raise ReleaseNotFoundError(f"{release_id} is not a release of {tenant_id}")
    existing = await session.scalar(
        select(RepositoryReleaseDocument.release_id).where(
            RepositoryReleaseDocument.release_id == release_id,
            RepositoryReleaseDocument.tenant_id == tenant_id,
        )
    )
    if existing is not None:
        raise ReleaseDocumentExistsError(f"release {release_id} already has its document")

    document, files = release_document.encode(content)
    data = release_document.dumps(document)
    names = sorted(files)
    held = set(
        await session.scalars(
            select(RepositoryReleaseBlob.sha256).where(
                RepositoryReleaseBlob.tenant_id == tenant_id,
                RepositoryReleaseBlob.sha256.in_(names),
            )
        )
    )
    new = [name for name in names if name not in held]
    for start in range(0, len(new), _BATCH):
        await session.execute(
            insert(RepositoryReleaseBlob)
            .values(
                [
                    {"tenant_id": tenant_id, "sha256": name, "data": files[name]}
                    for name in new[start : start + _BATCH]
                ]
            )
            .on_conflict_do_nothing()
        )
    session.add(
        RepositoryReleaseDocument(
            release_id=release_id,
            tenant_id=tenant_id,
            format=release_document.FORMAT,
            content=data,
            blobs=names,
        )
    )
    await session.flush()
    return StoredDocument(release_id, release_document.FORMAT, len(data), len(names), len(new))


async def read_release_content(
    session: AsyncSession, *, tenant_id: uuid.UUID, release_id: uuid.UUID
) -> Content:
    """The `Content` of a release of the repository `tenant_id`, as it was written."""
    row = (
        await session.execute(
            select(
                RepositoryReleaseDocument.format,
                RepositoryReleaseDocument.content,
                RepositoryReleaseDocument.blobs,
            ).where(
                RepositoryReleaseDocument.release_id == release_id,
                RepositoryReleaseDocument.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise ReleaseDocumentNotFoundError(f"no document of release {release_id}")
    format_, data, names = row
    files = {
        sha256: bytes(blob)
        for sha256, blob in await session.execute(
            select(RepositoryReleaseBlob.sha256, RepositoryReleaseBlob.data).where(
                RepositoryReleaseBlob.tenant_id == tenant_id,
                RepositoryReleaseBlob.sha256.in_(names),
            )
        )
    }
    content = release_document.decode(release_document.loads(bytes(data)), files, format=format_)
    if content.tenant_id != tenant_id:
        raise ReleaseDocumentCorruptError(
            f"the document of release {release_id} holds the content of {content.tenant_id}"
        )
    return content


async def read_release_copies(
    session: AsyncSession, *, tenant_id: uuid.UUID, release_id: uuid.UUID
) -> set[uuid.UUID]:
    """The repositories the repository had copied when the release was made: the one part of a
    document the manifest wants, read without the files or the rest (RFC 0037 §4)."""
    row = (
        await session.execute(
            select(RepositoryReleaseDocument.format, RepositoryReleaseDocument.content).where(
                RepositoryReleaseDocument.release_id == release_id,
                RepositoryReleaseDocument.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise ReleaseDocumentNotFoundError(f"no document of release {release_id}")
    format_, data = row
    if format_ not in release_document.READERS:
        raise release_document.UnknownDocumentFormatError(
            f"no reader for release documents of format {format_}"
        )
    try:
        return {
            uuid.UUID(copied) for copied in release_document.loads(bytes(data))["links"]["copies"]
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ReleaseDocumentCorruptError(
            f"the document of release {release_id} does not say what it was built on: {error!r}"
        ) from error
