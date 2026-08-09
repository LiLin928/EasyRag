"""Storage 抽象（本地 FS）单元测试。"""
import os

import pytest

from app.providers.storage.factory import get_storage


@pytest.mark.asyncio
async def test_put_get_roundtrip(tmp_path, monkeypatch):
    """put/get 往返一致，文件落到 storage_local_dir/key。"""
    monkeypatch.setattr("app.config.settings.storage_local_dir", str(tmp_path))
    st = get_storage()
    key = "kb1/doc1/a.pdf"
    await st.put(key, b"hello-bytes")
    data = await st.get(key)
    assert data == b"hello-bytes"
    assert os.path.exists(os.path.join(str(tmp_path), key))
