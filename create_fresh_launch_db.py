from pathlib import Path
import os, shutil, datetime, importlib.util

root=Path(__file__).resolve().parents[1]
server_path=root/"server.py"
db=Path(os.environ.get("EBL_DB_PATH",root/"ebl.db"))
archive_dir=Path(os.environ.get("EBL_ARCHIVE_DIR",root/"archives"))
archive_dir.mkdir(parents=True,exist_ok=True)

if db.exists():
    stamp=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    archive=archive_dir/f"genesis_archive_{stamp}.db"
    shutil.copy2(db,archive)
    print(f"Archived Genesis DB to {archive}")
    db.unlink()

spec=importlib.util.spec_from_file_location("ebl_server",server_path)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.init_db()
print(f"Fresh launch database initialized at {db}")
