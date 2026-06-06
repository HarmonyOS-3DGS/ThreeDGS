"""抽象接口定义 — 供 Core 层及上层统一依赖。

使用 typing.Protocol 定义接口，避免运行时继承开销，
同时让 IDE 和类型检查器提供完整的类型提示。
"""
from typing import Protocol


class StorageClient(Protocol):
    """存储客户端协议 — 统一本地文件系统与对象存储的接口。"""

    def upload_file(self, object_name: str, file_path: str) -> str:
        """上传本地文件到存储，返回存储路径/对象标识。"""
        ...

    def download_file(self, object_name: str, file_path: str) -> str:
        """从存储下载到本地文件路径。"""
        ...

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """获取预签名访问 URL。"""
        ...

    def delete_object(self, object_name: str) -> None:
        """删除存储对象。"""
        ...

    def put_object(self, object_name: str, data: bytes) -> str:
        """直接写入 bytes 到存储，返回存储路径。"""
        ...

    def list_objects(self, prefix: str = "") -> list[str]:
        """列出指定前缀下的所有对象名称。"""
        ...

    def object_exists(self, object_name: str) -> bool:
        """判断对象是否存在。"""
        ...

    def get_object_size(self, object_name: str) -> int:
        """获取对象大小（字节）。"""
        ...
