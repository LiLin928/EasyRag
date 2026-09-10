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

    @pytest.mark.asyncio
    async def test_get_metadata(self, storage):
        """测试获取文件元数据。"""
        content = b"Hello, Metadata!"
        key = "test/metadata.txt"

        await storage.upload(key, content)

        metadata = await storage.get_metadata(key)
        assert metadata is not None
        assert metadata["size"] == len(content)
        assert metadata["content_type"] == "application/octet-stream"
        assert metadata["last_modified"] is not None
        assert metadata["etag"] is None  # 本地存储没有 etag
        assert metadata["metadata"] == {}

    @pytest.mark.asyncio
    async def test_get_metadata_nonexistent(self, storage):
        """测试获取不存在文件的元数据。"""
        metadata = await storage.get_metadata("nonexistent/file.txt")
        assert metadata is None

    @pytest.mark.asyncio
    async def test_list_objects(self, storage):
        """测试列出文件。"""
        # 创建多个文件
        await storage.upload("file1.txt", b"content1")
        await storage.upload("dir/file2.txt", b"content2")
        await storage.upload("dir/file3.txt", b"content3")

        # 列出所有文件
        objects = await storage.list_objects(recursive=True)
        assert len(objects) == 3
        assert "file1.txt" in objects
        assert "dir/file2.txt" in objects
        assert "dir/file3.txt" in objects

        # 非递归列出
        objects = await storage.list_objects(recursive=False)
        assert len(objects) == 1
        assert "file1.txt" in objects

        # 按前缀过滤
        objects = await storage.list_objects(prefix="dir/", recursive=True)
        assert len(objects) == 2
        assert "dir/file2.txt" in objects
        assert "dir/file3.txt" in objects

    @pytest.mark.asyncio
    async def test_list_objects_empty_prefix(self, storage):
        """测试空前缀列出文件。"""
        await storage.upload("test.txt", b"content")

        objects = await storage.list_objects(prefix="", recursive=True)
        assert len(objects) == 1
        assert "test.txt" in objects

    @pytest.mark.asyncio
    async def test_copy(self, storage):
        """测试复制文件。"""
        content = b"Copy me!"
        source_key = "test/source.txt"
        dest_key = "test/destination.txt"

        await storage.upload(source_key, content)

        result = await storage.copy(source_key, dest_key)
        assert result is not None

        # 验证目标文件存在且内容相同
        downloaded = await storage.download(dest_key)
        assert downloaded == content

        # 验证源文件仍然存在
        assert await storage.exists(source_key)

    @pytest.mark.asyncio
    async def test_copy_nonexistent_source(self, storage):
        """测试复制不存在的文件。"""
        with pytest.raises(FileNotFoundError):
            await storage.copy("nonexistent.txt", "destination.txt")

    @pytest.mark.asyncio
    async def test_get_presigned_url(self, storage):
        """测试获取预签名 URL（本地存储不支持）。"""
        await storage.upload("test.txt", b"content")

        with pytest.raises(NotImplementedError):
            await storage.get_presigned_url("test.txt")

    @pytest.mark.asyncio
    async def test_get_size(self, storage):
        """测试获取文件大小。"""
        content = b"Size test content"
        key = "test/size.txt"

        await storage.upload(key, content)

        size = await storage.get_size(key)
        assert size == len(content)

    @pytest.mark.asyncio
    async def test_get_size_nonexistent(self, storage):
        """测试获取不存在文件的大小。"""
        with pytest.raises(FileNotFoundError):
            await storage.get_size("nonexistent.txt")


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
