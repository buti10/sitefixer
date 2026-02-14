import stat
from datetime import datetime

def list_dir(sftp, path):
    items = []
    for attr in sftp.listdir_attr(path):
        is_dir = stat.S_ISDIR(attr.st_mode)
        items.append({
            "name": attr.filename,
            "path": f"{path.rstrip('/')}/{attr.filename}",
            "type": "dir" if is_dir else "file",
            "size": attr.st_size,
            "modified": datetime.fromtimestamp(attr.st_mtime).isoformat(),
            "permissions": oct(attr.st_mode & 0o777),
        })
    return items
