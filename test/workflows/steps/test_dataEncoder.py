import pickle
import shutil
from unittest import TestCase

from source.data_model.dataset.RepertoireDataset import RepertoireDataset
from source.data_model.metadata.Sample import Sample
from source.data_model.receptor.receptor_sequence.ReceptorSequence import ReceptorSequence
from source.data_model.repertoire.RepertoireMetadata import RepertoireMetadata
from source.data_model.repertoire.SequenceRepertoire import SequenceRepertoire
from source.encodings.EncoderParams import EncoderParams
from source.encodings.word2vec.Word2VecEncoder import Word2VecEncoder
from source.encodings.word2vec.model_creator.ModelType import ModelType
from source.environment.EnvironmentSettings import EnvironmentSettings
from source.environment.LabelConfiguration import LabelConfiguration
from source.util.PathBuilder import PathBuilder
from source.workflows.steps.DataEncoder import DataEncoder
from source.workflows.steps.DataEncoderParams import DataEncoderParams


class TestDataEncoder(TestCase):
    def test_run(self):
        path = EnvironmentSettings.root_path + "test/tmp/dataencoder/"
        PathBuilder.build(path)

        rep1 = SequenceRepertoire(sequences=[ReceptorSequence("AAA")],
                                  metadata=RepertoireMetadata(Sample(1), custom_params={"l1": 1, "l2": 2}))
        with open(path + "rep1.pkl", "wb") as file:
            pickle.dump(rep1, file)

        rep2 = SequenceRepertoire(sequences=[ReceptorSequence("ATA")],
                                  metadata=RepertoireMetadata(Sample(2), custom_params={"l1": 0, "l2": 3}))
        with open(path + "rep2.pkl", "wb") as file:
            pickle.dump(rep2, file)

        lc = LabelConfiguration()
        lc.add_label("l1", [1, 2])
        lc.add_label("l2", [0, 3])

        dataset = RepertoireDataset(filenames=[path + "rep1.pkl", path + "rep2.pkl"])
        encoder = Word2VecEncoder.create_encoder(dataset, {
                    "k": 3,
                    "model_type": ModelType.SEQUENCE,
                    "vector_size": 6
                })

        res = DataEncoder.run(DataEncoderParams(
            dataset=dataset,
            encoder=encoder,
            encoder_params=EncoderParams(
                model={},
                batch_size=2,
                label_configuration=lc,
                result_path=path,
                filename="dataset.csv"
            )
        ))

        self.assertTrue(isinstance(res, RepertoireDataset))
        self.assertTrue(res.encoded_data.examples.shape[0] == 2)

        shutil.rmtree(path)
