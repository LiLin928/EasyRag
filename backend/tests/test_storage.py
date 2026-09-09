"""存储抽象层测试。"""
import tempfile
import pytest
import pytest_asyncio
from app.core.storage.interface import StorageInterface
from app.core.storage.local import LocalStorage
from app.core.storage import get_storage


class TestLocalStorage:
    """测试本地存储实现。"""

    @pytest_asyncio.fixture
    async def storage(self):
        """创建临时目录的 LocalStorage 实例。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield LocalStorage(tmpdir)

    @pytest.mark.asyncio
    async def test_upload_and_download(self, storage):
        """测试上传和下载功能。"""
        content = b"Hello, World!"
        key = "test/hello.txt"
        
        url = await storage.upload(key, content)
        assert url is not None
        
        downloaded = await storage.download(key)
        assert downloaded == content

    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """测试删除功能。"""
        content = b"Delete me"
        key = "test/delete.txt"
        
        await storage.upload(key, content)
        await storage.delete(key)
        
        exists = await storage.exists(key)
        assert not exists

    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """测试文件存在性检查。"""
        key = "test/exists.txt"
        
        assert not await storage.exists(key)
        
        await storage.upload(key, b"content")
        assert await storage.exists(key)

    @pytest.mark.asyncio
    async def test_nested_paths(self, storage):
        """测试嵌套路径。"""
        key = "deep/nested/path/file.txt"
        content = b"nested content"
        
        await storage.upload(key, content)
        downloaded = await storage.download(key)
        assert downloaded == content


class TestStorageInterface:
    """测试存储接口契约。"""

    def test_local_storage_implements_interface(self):
        """验证 LocalStorage 实现了 StorageInterface。"""
        storage = LocalStorage("/tmp")
        assert isinstance(storage, StorageInterface)


class TestStorageFactory:
    """测试存储工厂函数。"""

    def test_get_storage_returns_instance(self):
        """测试 get_storage 返回存储实例。"""
        storage = get_storage()
        assert storage is not None
        assert isinstance(storage, StorageInterface)

    def test_get_storage_singleton(self):
        """测试 get_storage 返回单例。"""
        storage1 = get_storage()
        storage2 = get_storage()
        assert storage1 is storage2
