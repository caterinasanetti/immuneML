import copy

from source.data_model.dataset.Dataset import Dataset
from source.encodings.EncoderParams import EncoderParams
from source.environment.LabelConfiguration import LabelConfiguration
from source.hyperparameter_optimization.HPSetting import HPSetting
from source.hyperparameter_optimization.SplitConfig import SplitConfig
from source.hyperparameter_optimization.strategy.HPOptimizationStrategy import HPOptimizationStrategy
from source.ml_methods.MLMethod import MLMethod
from source.reports.Report import Report
from source.reports.data_reports.DataReport import DataReport
from source.reports.ml_reports.MLReport import MLReport
from source.util.PathBuilder import PathBuilder
from source.workflows.processes.InstructionProcess import InstructionProcess
from source.workflows.processes.MLProcess import MLProcess
from source.workflows.steps.DataEncoder import DataEncoder
from source.workflows.steps.DataEncoderParams import DataEncoderParams
from source.workflows.steps.DataSplitter import DataSplitter
from source.workflows.steps.DataSplitterParams import DataSplitterParams
from source.workflows.steps.MLMethodAssessment import MLMethodAssessment
from source.workflows.steps.MLMethodAssessmentParams import MLMethodAssessmentParams
from source.workflows.steps.MLMethodTrainer import MLMethodTrainer
from source.workflows.steps.MLMethodTrainerParams import MLMethodTrainerParams


class HPOptimizationProcess(InstructionProcess):
    """
    Class implementing hyper-parameter optimization and nested model training and assessment:

    The process is defined by two loops:
        - the outer loop over defined splits of the dataset for performance assessment
        - the inner loop over defined hyper-parameter space and with cross-validation or train & validation split
          to choose the best hyper-parameters

    Optimal model chosen by the inner loop is then retrained on the whole training dataset in the outer loop.

    """

    def __init__(self, dataset: Dataset, hp_strategy: HPOptimizationStrategy, hp_settings: list,
                 assessment: SplitConfig, selection: SplitConfig, metrics: set,
                 label_configuration: LabelConfiguration, path: str = None):
        self.dataset = dataset
        self.selection = selection
        self.hp_strategy = hp_strategy
        assert all(isinstance(hp_setting, HPSetting) for hp_setting in hp_settings), \
            "HPOptimizationProcess: object of other type passed in instead of HPSetting."
        self.hp_settings = hp_settings
        self.path = path
        self.batch_size = 10
        self.label_configuration = label_configuration
        self.metrics = metrics
        self.assessment = assessment

    def run(self):
        return self.run_assessment()

    def run_assessment(self):
        train_datasets, test_datasets = self.split_data(self.dataset, self.assessment)
        fold_performances = []
        for index in range(self.assessment.split_count):
            fold_performances.append(self.run_assessment_fold(train_datasets[index], test_datasets[index], index + 1))
        self.print_performances(performances=fold_performances)
        return fold_performances

    def run_assessment_fold(self, train_dataset: Dataset, test_dataset: Dataset, run):
        current_path = "{}assessment_{}/run_{}/".format(self.path, self.assessment.split_strategy.name, run)
        PathBuilder.build(current_path)
        optimal_hp_setting = self.run_selection(train_dataset, current_path)
        encoded_train_dataset = self.encode_dataset(train_dataset, optimal_hp_setting, current_path, learn_model=True)
        optimal_method = self.train_optimal_method(encoded_train_dataset, optimal_hp_setting, current_path + "optimal/")
        encoded_test_dataset = self.encode_dataset(test_dataset, optimal_hp_setting, current_path, learn_model=False)
        performance = self.assess_performance(optimal_method, encoded_test_dataset, run, current_path)
        self.run_assessment_reports(train_dataset, test_dataset, optimal_method, current_path + "reports/")
        return performance

    def run_selection(self, train_dataset: Dataset, current_path: str) -> HPSetting:
        train_datasets, test_datasets = self.split_data(train_dataset, self.selection)
        path = "{}selection_{}/".format(current_path, self.selection.split_strategy.name)
        PathBuilder.build(path)
        hp_setting = self.hp_strategy.get_next_setting()
        while hp_setting is not None:
            performance = self.test_hp_setting(hp_setting, train_datasets, test_datasets, path)
            hp_setting = self.hp_strategy.get_next_setting(hp_setting, performance)

        self.run_selection_reports(train_dataset, train_datasets, test_datasets, path + "reports/")
        return self.hp_strategy.get_optimal_hps()

    def test_hp_setting(self, hp_setting, train_datasets: list, test_datasets: list, current_path: str) -> dict:
        fold_performances = []
        for index in range(self.selection.split_count):
            fold_performances.append(self.run_setting(hp_setting, train_datasets[index], test_datasets[index], index + 1, current_path))
        return self.get_average_performance(fold_performances)

    def run_setting(self, hp_setting, train_dataset, test_dataset, run_id: int, current_path: str):
        path = current_path + "{}/fold_{}/".format(hp_setting, run_id)
        PathBuilder.build(path)
        ml_process = MLProcess(train_dataset=train_dataset, test_dataset=test_dataset,
                               label_configuration=self.label_configuration, encoder=hp_setting.encoder,
                               encoder_params=hp_setting.encoder_params, method=hp_setting.ml_method,
                               ml_params=hp_setting.ml_params, metrics=self.metrics, path=path,
                               reports=self.selection.reports.model_reports)
        performance = ml_process.run(run_id)
        return performance

    def run_assessment_reports(self, train_dataset: Dataset, test_dataset: Dataset, method: MLMethod, path: str):
        for report in self.assessment.reports.data_split_reports:
            self.run_data_report(report, train_dataset, path + "train/")
            self.run_data_report(report, test_dataset, path + "test/")

        for report in self.assessment.reports.optimal_model_reports:
            self.run_model_report(report, train_dataset, test_dataset, method, path)

        for report in self.assessment.reports.performance_reports:
            self.run_performance_report(report, method, train_dataset, test_dataset, path)

    def run_selection_reports(self, dataset: Dataset, train_datasets: list, test_datasets: list, path: str):
        for report in self.selection.reports.data_split_reports:
            for index in range(len(train_datasets)):
                self.run_data_report(report, train_datasets[index], path + "split_{}/train/".format(index+1))
                self.run_data_report(report, test_datasets[index], path + "split_{}/test/".format(index+1))
        for report in self.selection.reports.data_reports:
            self.run_data_report(report, dataset, path)

    def run_performance_report(self, report: Report, method: MLMethod, train_dataset: Dataset, test_dataset: Dataset, path: str):
        # TODO: performance reports should be only on results from test set predictions - update
        raise NotImplementedError

    def run_model_report(self, report: MLReport, train_dataset: Dataset, test_dataset: Dataset, method: MLMethod, path: str):
        tmp_report = copy.deepcopy(report)
        tmp_report.train_dataset = train_dataset
        tmp_report.test_dataset = test_dataset
        tmp_report.method = method
        tmp_report.path = path
        tmp_report.generate_report()

    def run_data_report(self, report: DataReport, dataset: Dataset, path: str):
        tmp_report = copy.deepcopy(report)
        tmp_report.dataset = dataset
        tmp_report.path = path
        tmp_report.generate_report()

    def split_data(self, dataset, split_config: SplitConfig) -> tuple:
        params = DataSplitterParams(
            dataset=dataset,
            split_strategy=split_config.split_strategy,
            split_count=split_config.split_count,
            training_percentage=split_config.training_percentage,
            label_to_balance=split_config.label_to_balance
        )
        return DataSplitter.run(params)

    def get_average_performance(self, metrics_per_label):
        return {label: sum(perf[label] for perf in metrics_per_label) / len(metrics_per_label)
                for label in self.label_configuration.get_labels_by_name()}

    def train_optimal_method(self, dataset: Dataset, hp_setting: HPSetting, path: str) -> MLMethod:
        method = MLMethodTrainer.run(MLMethodTrainerParams(
            method=hp_setting.ml_method,
            result_path=path + "/ml_method/",
            dataset=dataset,
            labels=self.label_configuration.get_labels_by_name(),
            model_selection_cv=hp_setting.ml_params["model_selection_cv"],
            model_selection_n_folds=hp_setting.ml_params["model_selection_n_folds"],
            cores_for_training=-1  # TODO: make it configurable, add cores_for_training
        ))
        return method

    def encode_dataset(self, dataset: Dataset, hp_setting: HPSetting, path: str, learn_model: bool) -> Dataset:
        encoded_dataset = DataEncoder.run(DataEncoderParams(
            dataset=dataset,
            encoder=hp_setting.encoder,
            encoder_params=EncoderParams(
                model=hp_setting.encoder_params,
                result_path=path,
                batch_size=self.batch_size,
                label_configuration=self.label_configuration,
                learn_model=learn_model,
                filename="train_dataset.pkl" if learn_model else "test_dataset.pkl"
            )
        ))
        return encoded_dataset

    def assess_performance(self, optimal_method, dataset, run, current_path):
        return MLMethodAssessment.run(MLMethodAssessmentParams(
            method=optimal_method,
            dataset=dataset,
            predictions_path="{}predictions.csv".format(current_path),
            all_predictions_path="{}assessment_{}/all_predictions.csv".format(self.path, self.assessment.split_strategy.name),
            ml_details_path="{}ml_details.csv".format(current_path),
            run=run,
            label_configuration=self.label_configuration,
            metrics=self.metrics,
            path=current_path
        ))

    def print_performances(self, performances: list):
        print("------ Assessment scores (balanced accuracy) per label ------")
        header = "run\t"
        for label in self.label_configuration.get_labels_by_name():
            header += label + "\t"
        print(header)
        for index, performance in enumerate(performances):
            row = str(index + 1) + "\t"
            for label in self.label_configuration.get_labels_by_name():
                row += str(performance[label]) + "\t"
            print(row)
        print("--------------------------------------------------------------")
        for label in self.label_configuration.get_labels_by_name():
            print("Label: {}, average balanced accuracy: {}".format(label,
                                                                    sum(perf[label] for perf in performances) /
                                                                    len(performances)))
