import logging
logger = logging.getLogger(__name__)

import os
import json
import pandas as pd
import flatten_json


class VNFBR:
    def __init__(self):
        self.vnfpp = {}
        self.vnfbd = {}

    def _extract_metrics(self, metrics):
        def parse_metrics(col, values):
            metrics = {}
            for k,v in values.items():
                name = "_".join(["metric", col, k])
                metrics[name] = v 
            return metrics

        metrics_summary = {}       
        df = pd.DataFrame(metrics)
        metrics_names = list(df.columns.values)

        for metric_name in metrics_names:
            desc = df[metric_name].describe()
            dict_desc = desc.to_dict()
            col_metrics = parse_metrics(metric_name, dict_desc)
            metrics_summary.update(col_metrics)

        return metrics_summary

    def _extract_evals(self, evals, prefix, test, trial):
        metrics = {
            "test": test,
            "trial": trial,
        }

        general_metrics = {}
        for ev in evals:
            is_series = ev.get("series")
            ev_metrics = ev.get("metrics")

            if is_series:
                metrics_summary = self._extract_metrics(ev_metrics)
            else:
                metrics_summary = {"metric_" + k: v for k, v in ev_metrics.items()}
            
            general_metrics.update(metrics_summary)

        metrics_frmt = {prefix + "_" + k: v for k, v in general_metrics.items()}
        metrics.update(metrics_frmt)

        return metrics

    def _extract_snaps(self, snaps, test):
        metrics = {} 
        for snap in snaps:
            snap_trial = snap.get("trial")
            snap_role = snap.get("role")          
            evals = snap.get("evaluations")
            evals_metrics = self._extract_evals(evals, snap_role, test, snap_trial)
            metrics.update(evals_metrics)
        return metrics

    def _extract_report(self, report):
        metrics = {}
        report_test = report.get("test")       
        report_inputs = report.get("inputs")
        snaps = report.get("snapshots")

        inputs = flatten_json.flatten(report_inputs)
        inputs_frmt = {"input_" + k: v for k, v in inputs.items()}
        
        metrics = self._extract_snaps(snaps, report_test)
        metrics.update(inputs_frmt)
        return metrics

    def extract(self, dataframe=True):
        flat_report_metrics = []
        if self.vnfpp:
            reports = self.vnfpp.get("reports")

            flat_report_metrics = []
            for report in reports:
                filtered_report_metrics = self._extract_report(report)
                flat_report_metrics.append(filtered_report_metrics)
        else:
            logger.info("No vnfbr loaded")

        if dataframe:
            df = pd.DataFrame(flat_report_metrics)
            return df
        else:
            return flat_report_metrics

    def _load_file(self, filepath):
        data = {}
        with open(filepath, 'r') as fp:
            data = json.load(fp)
            return data
        return data

    def load(self, filepath):
        vnfbr = self._load_file(filepath)
        if vnfbr:
            self.vnfpp = vnfbr.get("result").get("vnfpp")
            self.vnfbd = vnfbr.get("result").get("vnfbd")
        else:
            logger.info("Could not load vnfbr - filepath %s", filepath)