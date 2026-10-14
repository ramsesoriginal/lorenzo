# Source this in WSL: points the app at the spike database.
export DATABASE_URL=postgresql+asyncpg://lorenzo_app:lorenzo_app@localhost:55432/lorenzo_r2
export MIGRATIONS_DATABASE_URL=postgresql+asyncpg://lorenzo:lorenzo@localhost:55432/lorenzo_r2
export R2_STATE_DIR=$HOME/lorenzo-r2/state
export R2_RESULT_DIR=$HOME/lorenzo-r2/results
