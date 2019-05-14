import logging
logger = logging.getLogger(__name__)

import os
from functools import reduce

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from gym.common.info import Content


class View:
    GFX_FOLDER = './gfx/'
    CSV_FOLDER = './csv/'
    PREFIX = 'vnfpp_'

    def __init__(self):
        self.folder = None
        self.prefix = None
        self.images_path = None
        self.set(self.GFX_FOLDER, self.CSV_FOLDER, self.PREFIX)
        self._filename = None
        self._series_suffix = None

    def set_filename(self, filename):
        self._filename = filename

    def set_filesuffix_series(self, suffix):
        self._series_suffix = suffix

    def set(self, gfx_folder, csv_folder, prefix):
        self.folder = gfx_folder
        self.data_folder = csv_folder
        self.prefix = prefix
        self.images_path = self.folder 
        if not os.path.exists(os.path.dirname(self.images_path)):
            os.makedirs(os.path.dirname(self.images_path))
        if not os.path.exists(os.path.dirname(self.data_folder)):
            os.makedirs(os.path.dirname(self.data_folder))

    def parse_save_series(self, data, filename_suffix):
        ext = '.csv'
        series_data = pd.DataFrame(data)
        filename = self._filename + '_' + str(self._series_suffix) + '_series_' + filename_suffix
        filepath = self.data_folder + filename + ext
        series_data.to_csv(filepath)
        logger.info("series_data view saved to %s", filepath)
    
    def parse_save_dataframe(self, data):
        data = pd.DataFrame(data)
        ext = '.csv'
        filepath = self.data_folder + self._filename + ext
        data.to_csv(filepath)
        logger.info("vnfpp view saved to %s", filepath)
    
    def parse(self, data):
        self.data = pd.DataFrame(data)

    def save(self, filename):
        ext = '.csv'
        filepath = self.data_folder + filename + ext
        self.data.to_csv(filepath)
        logger.info("vnfpp view saved to %s", filepath)
    
    def load(self, filename):
        ext = '.csv'
        filepath = self.data_folder + filename + ext
        self.data = pd.read_csv(filepath)

    def get_data(self):
        return self.data
        
    def head(self):
        print(self.data.head())

    def info(self):
        print(self.data.info())

    def describe(self):
        print(self.data.describe())

    def save_fig(self, fig_id, tight_layout=True, fig_extension="png", fig_size=(8, 6), resolution=300):
        path = os.path.join(self.images_path, fig_id + "." + fig_extension)
        print("Saving figure", fig_id)
        if tight_layout:
            plt.tight_layout()
        plt.savefig(path, format=fig_extension, figsize=fig_size, dpi=resolution)
        self.finish()

    def finish(self):
        plt.cla()
        plt.clf()
        plt.close()

    def hist(self, feature):
        filename = self.prefix + "hist"
        self.data.hist(bins=100, column=feature, figsize=(20, 15))
        plt.xlim([.5, 1.0])
        self.save_fig(filename)

    def scatter(self, x, y, hue, col):
        filename = self.prefix + "scatterplot"
        self.data.plot(kind="scatter", x=x, y=y, alpha=0.4,
              s=self.data[hue], label=hue, figsize=(10, 7),
              c=col, cmap=plt.get_cmap("jet"), colorbar=True,
              sharex=False)
        plt.legend()
        self.save_fig(filename)

    def factorplot(self, x, y, col, hue=None):
        filename = self.prefix + 'factorplot'
        g = sns.factorplot(x=x,
                       y=y,
                       data=self.data,
                       hue=hue,  # Color by stage
                       col=col,  # Separate by stage
                       kind='swarm',
                       size=8,
                       aspect=1.2,
                       legend_out=True)  # Swarmplot
        # box = g.ax.get_position()  # get position of figure
        # g.ax.set_position([box.x0, box.y0, box.width * 0.85, box.height])  # resize position
        # # Put a legend to the right side
        # g.ax.legend(loc='center right', bbox_to_anchor=(1.25, 0.5), ncol=1)

        # plt.legend(bbox_to_anchor=(1, 1), loc=2)
        # ax.legend(ncol=1, loc="lower right", frameon=False)
        # ax.despine(left=True)
        self.save_fig(filename)

    def jointplot(self, feat1, feat2):
        filename = self.prefix + 'jointplot'
        sns.jointplot(x=feat1, y=feat2, data=self.data, kind="reg",
                      marginal_kws = dict(bins=15, rug=True), annot_kws = dict(stat="r"))
        self.save_fig(filename)

    def swarmplot(self, feat1, feat2, hue=None):
        filename = self.prefix + 'swarmplot'
        sns.swarmplot(x=feat1, y=feat2, data=self.data, hue=hue)
        self.save_fig(filename)


class VNFPP(Content):
    def __init__(self):
        Content.__init__(self)
        self.id = None
        self._instance = None
        self._reports = {}
        self._vnfbd_instances = {}
        self.reports = []
        self._view = View()
        self.view_desc = {}

    def set_id(self, instance_id):
        self.id = instance_id
    
    def get_id(self):
        return self.id

    def add_report(self, vnfbd, report):
        report_id = report.get_id()
        self._reports[report_id] = report
        self._vnfbd_instances[report_id] = vnfbd

    def compile(self, layout_id=None):
        logger.info("VNFPP compilation")
        self._instance = layout_id
        for report_id,report in self._reports.items(): 
            snapshots = report.get('snapshots')
            snaps = list(map(self._process_snapshot, snapshots))
            keywords = ['id', 'role', 'host', 'component', 'timestamp']
            profile = self._retrieve_dict(report, keywords)
            profile['snapshots'] = snaps
            vnfbd = self._vnfbd_instances.get(report_id)
            profile['inputs'] = vnfbd.get_inputs()
            self.reports.append(profile)
        self.views(self.reports, self.view_desc)

    def has_list_value(self, dict_items):
        fields_list = [ field for field,value in dict_items.items() if type(value) is list ]
        return fields_list

    def has_dict_value(self, inputs):
        fields_dict = [ field for field,value in inputs.items() if type(value) is dict ]
        return fields_dict

    def lists_paths(self, inputs, internal=False):
        full_paths = []
        dicts = self.has_dict_value(inputs)
        if dicts:
            for dict_field in dicts:
                paths = self.lists_paths(inputs[dict_field], internal=True)
                if paths:
                    if all([True if type(path) is list else False for path in paths]):
                        for path in paths:
                            paths_partial = [dict_field]
                            paths_partial.extend(path)
                            full_paths.append(paths_partial)
                    else:
                        paths_partial = [dict_field]
                        paths_partial.extend(paths)
                        if internal:
                            full_paths.extend(paths_partial)
                        else:
                            full_paths.append(paths_partial)
        lists = self.has_list_value(inputs)
        if lists:
            for list_field in lists:
                full_paths.append( [list_field, inputs[list_field]] )
        return full_paths

    def parse_inputs(self, inputs):
        logger.info("vnfpp parse_inputs")
        # fields_list = [ field for field,value in inputs.items() if type(value) is list ]
        # logger.info("fields_list %s", fields_list)        
        lists_paths = self.lists_paths(inputs)
        logger.info("lists_paths %s", lists_paths)
        self.view_desc = {
            'filename': 'vnfpp_',
            # 'inputs': fields_list,
            'inputs': lists_paths,
            'metrics': {
                'agent': 'all',
                'monitor': 'all',
            }
        }

    def _retrieve_dict(self, content, keywords):
        _dict = {}
        for key in keywords:
            value = content.get(key)
            _dict[key] = value
        return _dict

    def _process_evaluation(self, evaluation):
        keywords = ['id', 'tool', 'type', 'series', 'metrics', 'timestamp']
        eval = self._retrieve_dict(evaluation, keywords)
        return eval

    def _process_snapshot(self, snapshot):
        logger.info("_process_snapshot")
        keywords = ['id', 'role', 'host', 'component', 'timestamp']
        evaluations = snapshot.get('evaluations')
        evals = list(map(self._process_evaluation, evaluations))
        snap = self._retrieve_dict(snapshot, keywords)
        snap['evaluations'] = evals
        return snap

    def _filter_metric_float(self, metric_value):
        float_metric = 0.0
        try:
            float_metric = float(metric_value)
        except ValueError:
            logger.debug("Not a float %s", metric_value)
            float_metric = 0.0
        finally:
            return float_metric

    def _filter_metrics(self, eval_metrics, metrics):
        filtered_metrics = []
        if metrics == 'all':
            filter_metrics = eval_metrics.keys()
        else:
            filter_metrics = metrics
        
        not_metrics = ['timestamp'] 
        for metric in filter_metrics:
            eval_metric = eval_metrics.get(metric, None)
            if eval_metric and metric not in not_metrics:
                metric_dict = {
                    metric: self._filter_metric_float(eval_metric),
                }
                filtered_metrics.append( metric_dict )
        return filtered_metrics

    def _save_eval_series(self, evaluation):
        eval_metrics_series = evaluation.get("series")
        if eval_metrics_series:
            eval_metrics = evaluation.get("metrics")
            eval_tool = evaluation.get("tool")
            eval_type = evaluation.get("type")
            eval_suffix = eval_type + '_' + str(eval_tool) 
            self._view.parse_save_series(eval_metrics, eval_suffix)        

    def _filter_eval(self, evaluation, metrics):
        self._save_eval_series(evaluation)
        filtered_metrics = []
        eval_metrics = evaluation.get("metrics")
        if eval_metrics:
            eval_metrics_series = evaluation.get("series")
            if eval_metrics_series:
                for eval_metric in eval_metrics:
                    eval_filtered_metrics = self._filter_metrics(eval_metric, metrics)
                    filtered_metrics.extend(eval_filtered_metrics)

            else:
                eval_filtered_metrics = self._filter_metrics(eval_metrics, metrics)
                filtered_metrics.extend(eval_filtered_metrics)    
        return filtered_metrics

    def _filter_snap_evals(self, snap_filtered_metrics, snap_metrics):
        condensed_snap_metrics = []
        
        if snap_metrics == 'all':
            snap_proc_metrics = []
            eval_metric_lists = [eval_metric.keys() for eval_metric in snap_filtered_metrics]
            for metric_list in eval_metric_lists:
                snap_proc_metrics.extend(metric_list)
        else:
            snap_proc_metrics = snap_metrics
        
        for metric in snap_proc_metrics:
            metric_values = []
            for eval_metric in snap_filtered_metrics:
                value = eval_metric.get(metric)
                if value:
                    metric_values.append(value)
            if metric_values:
                metric_values_array = np.array(metric_values)
                snap_condensed_metric = {
                    metric + '_mean': np.mean(metric_values_array),
                    metric + '_std': np.std(metric_values_array),
                    metric + '_median': np.median(metric_values_array),
                    metric + '_min': np.amin(metric_values_array),
                    metric + '_max': np.amax(metric_values_array),
                }
                condensed_snap_metrics.append(snap_condensed_metric)
        return condensed_snap_metrics

    def _filter_snap(self, snaps, metrics):
        filtered_snap_metrics = []
        for snap_role, snap_metrics in metrics.items(): 
            snaps_by_role = filter(lambda snap: snap['role'] == snap_role, snaps)
            snap_filtered_metrics = []
            for snap in snaps_by_role:
                evals = snap.get("evaluations")
                for _eval in evals:
                    evals_filtered_metrics = self._filter_eval(_eval, snap_metrics) 
                    snap_filtered_metrics.extend(evals_filtered_metrics)
            
            condensed_snap_metrics = self._filter_snap_evals(snap_filtered_metrics, snap_metrics)
            filtered_snap_metrics.extend(condensed_snap_metrics)
        
        return filtered_snap_metrics

    def _merge_dicts(self, snap_list):
        init_dict = {}
        if snap_list:
            init_dict = snap_list.pop()
            for other_dict in snap_list:
                init_dict.update(other_dict)
        return init_dict

    def get_report_inputs(self, view_inputs, report_inputs):
        filtered_inputs = {}

        for view_input in view_inputs:
            path = view_input[:-1]        
            input_value = reduce(dict.__getitem__, path, report_inputs)
            input_name = "input_" + '_'.join(path)
            filtered_inputs[input_name] = input_value

        # logger.info("report filtered_inputs %s", filtered_inputs)
        return filtered_inputs

    def _filter_report(self, report, view_desc):
        filtered_inputs = {}
        report_inputs = report.get("inputs")
        view_inputs = view_desc.get("inputs")
        snaps = report.get("snapshots")
        
        # for _input in view_inputs:
        #     if _input in report_inputs:
        #         filtered_inputs[_input] = report_inputs.get(_input)
        filtered_inputs = self.get_report_inputs(view_inputs, report_inputs)
        
        report_id = report.get("id")
        self._view.set_filesuffix_series(report_id)

        filtered_report_metrics = self._filter_snap(snaps, view_desc.get("metrics"))
        for filtered_report in filtered_report_metrics:
            filtered_report.update(filtered_inputs)
            filtered_report["id"] = report_id
        return filtered_report_metrics

    def _filter_views(self, reports, view_desc):
        filtered_reports = []
        for report in reports:
            filtered_report_metrics = self._filter_report(report, view_desc)
            merged_report_metrics = self._merge_dicts(filtered_report_metrics)
            filtered_reports.append(merged_report_metrics)
        return filtered_reports

    def views(self, reports, view_desc):
        logger.info("vnfpp views %s", view_desc)
        name = view_desc.get("filename")
        filename = name + self.get_id()
        if self._instance:
            filename = filename + '_' + self._instance
        
        self._view.set_filename(filename)
        compiled_reports = self._filter_views(reports, view_desc)
        self._view.parse_save_dataframe(compiled_reports)
        # self._view.parse(compiled_reports)
        # self._view.save(filename)
        # self._view.info()
        # self._view.head()

    def load(self, filename):
        self._view.load(filename)
        
    def gfx(self):
        self._view.factorplot("vnf_vcpus", "cpu_percent_mean", "vm_config", hue="vnf_mem_size")
        # self._view.swarmplot("vnf_vcpus", "mem_percent_mean")
        # self._view.jointplot("mem_percent_mean", "bits_per_second_mean")
        # self._view.scatter("vnf_vcpus", "cpu_percent_mean", "mem_percent_mean", "vnf_mem_size")

    def data(self):
        return self._view.get_data()


