# quality: gold

import uuid
from collections.abc import Iterable

import pandas as pd

from source.data_model.encoded_data.EncodedData import EncodedData
from source.data_model.repertoire.RepertoireGenerator import RepertoireGenerator


class Dataset:

    def __init__(self, data: Iterable = None, params: dict = None, encoded_data: EncodedData = None,
                 filenames: list = None, identifier: str = None, metadata_file: str = None):
        self.data = data
        self.params = params
        self.encoded_data = encoded_data
        self.id = identifier if identifier is not None else uuid.uuid1()
        self._filenames = sorted(filenames) if filenames is not None else []
        self.metadata_file = metadata_file

    def add_data(self, data: Iterable):
        self.data = data

    def add_encoded_data(self, encoded_data: EncodedData):
        self.encoded_data = encoded_data

    def get_data(self, batch_size: int = 1):
        self._filenames.sort()
        return RepertoireGenerator.build_generator(file_list=self._filenames, batch_size=batch_size)

    def get_repertoire(self, index: int = -1, filename: str = ""):
        assert index != -1 or filename != "", "Dataset: cannot load repertoire since the index nor filename are set."
        return RepertoireGenerator.load_repertoire(filename if filename != "" else self._filenames[index])

    def get_repertoire_count(self):
        return len(self._filenames)

    def set_filenames(self, filenames: list):
        self._filenames = sorted(filenames)

    def get_filenames(self):
        return self._filenames

    def get_metadata(self, field_names: list):
        df = pd.read_csv(self.metadata_file, sep=",", usecols=field_names)
        return df.to_dict("list")
