import io
import os
import shutil
import tarfile
import tempfile
import zipfile
from abc import abstractmethod, ABCMeta
from typing import Callable, IO, Union, Optional

import chardet


class Archive(metaclass=ABCMeta):

    @abstractmethod
    def get_file_by_name(self, name: str) -> bytes:
        pass

    @abstractmethod
    def decompress(self, path: str) -> Optional[str]:
        pass

    @abstractmethod
    def decompress_by_name(self, name: str, path: str) -> None:
        pass

    @abstractmethod
    def iter(self, func: Callable[[str], None]) -> None:
        pass


class ZipArchive(Archive):

    def __init__(self, f: IO[bytes]):
        self._f = zipfile.ZipFile(file=f, mode='r')
        self._prefix = ''
        prefix = list(filter(lambda _n: _n.endswith(os.sep) and len(_n.split(os.sep)) == 2, self._f.namelist()))
        if len(prefix) == 1:
            self._prefix = prefix[0]

    def decompress(self, path: str):
        temp_path = tempfile.mkdtemp()
        self._f.extractall(temp_path)
        # 如果目录下没有文件 && 目录下只有一个文件夹
        while (len(list(filter(lambda f: os.path.isfile(os.path.join(temp_path, f)), os.listdir(temp_path)))) == 0 and
               len(os.listdir(temp_path)) == 1):
            temp_path = os.path.join(temp_path, os.listdir(temp_path)[0])
        shutil.move(temp_path, path)

    def decompress_by_name(self, name: str, path: str) -> None:
        if self._prefix is not None and len(self._prefix):
            p = os.path.join(path, name.replace(self._prefix, ''))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'wb') as fw:
                fw.write(self._f.read(name=name))
        else:
            self._f.extract(member=name, path=path)

    def get_file_by_name(self, name: str) -> bytes:
        return self._f.read(name=name)

    def iter(self, func: Callable[[str], None]):
        for name in self._f.namelist():
            func(name)


class TarArchive(Archive):
    def __init__(self, f: IO[bytes]):
        self._f = tarfile.open(fileobj=f)
        self._prefix = ''
        prefix = list(filter(lambda _n: len(_n.split(os.sep)) == 1, self._f.getnames()))
        if len(prefix) == 1:
            self._prefix = prefix[0]

    def decompress(self, path: str):
        temp_path = tempfile.mkdtemp()
        self._f.extractall(temp_path)
        # 如果目录下没有文件 && 目录下只有一个文件夹
        while (len(list(filter(lambda f: os.path.isfile(os.path.join(temp_path, f)), os.listdir(temp_path)))) == 0 and
               len(os.listdir(temp_path)) == 1):
            temp_path = os.path.join(temp_path, os.listdir(temp_path)[0])
        shutil.move(temp_path, path)

    def decompress_by_name(self, name: str, path: str) -> None:
        if self._prefix is not None and len(self._prefix):
            p = os.path.join(path, name.replace(self._prefix, ''))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with self._f.extractfile(member=name) as fr, open(p, 'wb') as fw:
                fw.write(fr.read())
        else:
            self._f.extract(member=name, path=path)

    def get_file_by_name(self, name: str) -> bytes:
        return self._f.extractfile(member=name).read()

    def iter(self, func: Callable[[str], None]):
        for name in self._f.getnames():
            func(name)


def resolve_archive(data: Union[bytes, IO[bytes]]) -> Archive:
    f: IO[bytes] = data
    if isinstance(data, bytes):
        f = io.BytesIO(data)
    archive = None
    # 如果是 zip 文件
    if zipfile.is_zipfile(f):
        archive = ZipArchive(f)
    # 如果是 tar 文件
    elif is_tarfile(f):
        archive = TarArchive(f)
    return archive


def is_tarfile(f: IO[bytes]) -> bool:
    try:
        f.seek(0)
        tarfile.open(fileobj=f, mode='r')
    except tarfile.TarError:
        return False
    f.seek(0)
    return True


def is_text(b):
    return chardet.detect(b)['encoding'] is not None
