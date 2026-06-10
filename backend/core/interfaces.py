"""抽象接口 — StorageClient Protocol。

为何用 typing.Protocol 而非 ABC：
  - Structural subtyping：实现了匹配方法签名即为子类型，无需显式继承
  - 零运行时开销：不做 isinstance 检查，不引入 metaclass
  - IDE/类型检查器（pyright/mypy）仍能提供完整类型提示和自动补全
  - LocalStorageClient 和 MinioStorageClient 无需 import 此模块
"""

from typing import Protocol


class StorageClient(Protocol):
    """存储客户端协议 — 统一本地文件系统与对象存储的接口。

    LocalStorageClient 和 MinioStorageClient 都实现了此接口的全部方法，
    通过 structural subtyping 自动满足协议约束。
    """

    def upload_file(self, object_name: str, file_path: str) -> str:
        """上传本地文件到存储，返回存储路径/对象标识。"""
        ...

    def download_file(self, object_name: str, file_path: str) -> str:
        """从存储下载到本地文件路径。"""
        ...

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """获取预签名 GET URL（下载用）。"""
        ...

    def get_presigned_put_url(self, object_name: str, expires: int = 3600) -> str:
        """获取预签名 PUT URL（上传用）。"""
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
