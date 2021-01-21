# quality: gold

import abc
from pathlib import Path
from source.data_model.dataset.Dataset import Dataset


class DataExporter(metaclass=abc.ABCMeta):

    @staticmethod
    @abc.abstractmethod
    def export(dataset: Dataset, path: Path):
        pass
