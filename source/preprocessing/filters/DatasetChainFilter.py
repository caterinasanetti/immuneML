import copy
import os

from source.data_model.dataset.RepertoireDataset import RepertoireDataset
from source.data_model.receptor.receptor_sequence.Chain import Chain
from source.preprocessing.filters.Filter import Filter
from source.util.PathBuilder import PathBuilder


class DatasetChainFilter(Filter):
    """
    Preprocessing filter which removes all repertoires from the RepertoireDataset object which contain at least one sequence
    from chain different than "keep_chain" parameter
    """

    def __init__(self, keep_chain: Chain, result_path: str = None):
        self.keep_chain = keep_chain
        self.result_path = result_path

    def process_dataset(self, dataset: RepertoireDataset, result_path: str = None):
        return DatasetChainFilter.process(dataset=dataset, params={"keep_chain": self.keep_chain,
                                                                   "result_path": result_path if result_path is not None
                                                                   else self.result_path})

    @staticmethod
    def process(dataset: RepertoireDataset, params: dict) -> RepertoireDataset:
        processed_dataset = copy.deepcopy(dataset)
        PathBuilder.build(params["result_path"])
        filenames = []
        indices = []
        for index, repertoire in enumerate(dataset.get_data()):
            if all(sequence.metadata.chain == Chain[params["keep_chain"].upper()] for sequence in repertoire.sequences):
                filename = params["result_path"] + "{}.pickle".format(repertoire.identifier)
                os.rename(dataset.get_filenames()[index], filename)
                filenames.append(filename)
                indices.append(index)

        processed_dataset.metadata_file = DatasetChainFilter.build_new_metadata(processed_dataset, indices, params["result_path"])
        processed_dataset.set_filenames(filenames)
        return processed_dataset
