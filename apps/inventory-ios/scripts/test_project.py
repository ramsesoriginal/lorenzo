import plistlib, subprocess, sys, unittest
from pathlib import Path
class ProjectTests(unittest.TestCase):
    def test_generated_project_has_app_and_native_test_target(self):
        root=Path(__file__).resolve().parent.parent
        subprocess.run([sys.executable,str(root/"scripts/project.py")],check=True,capture_output=True)
        project=plistlib.loads((root/"LorenzoInventory.xcodeproj/project.pbxproj").read_bytes())
        targets=[x for x in project["objects"].values() if x["isa"]=="PBXNativeTarget"]
        self.assertEqual({x["name"] for x in targets},{"LorenzoInventory","InventoryUITests"})
