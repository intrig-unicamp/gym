import logging
logger = logging.getLogger(__name__)

import os
import json
import pandas as pd

from gym.common.info import Content


class VNFBR(Content):
    def __init__(self, vnfbr_id):
        Content.__init__(self)
        self.id = vnfbr_id
        self.vnfpp = {}
        self.vnfbd = {}

    def set_attrib(self, attrib, data):
        if attrib == "vnfbd":
            self.vnfbd = data
        elif attrib == "vnfpp":
            self.vnfpp = data
        else:
            logger.info("unknown vnfbr attrib %s", attrib)

    def _extract_metrics(self, metrics, prefix, source, save=False):
        metrics_summary = {}     

        columns = [metric.get("name") for metric in metrics]
        data = { metric.get("name"):metric.get("value") for metric in metrics }
        df = pd.DataFrame(data=data)
        
        for metric_name in columns:
            desc = df[metric_name].describe()
            dict_desc = desc.to_dict()
            col_metrics = { "_".join([metric_name, k]):v for k,v in dict_desc.items() }
            metrics_summary.update(col_metrics)

        if save:
            dirname = "./csv"
            filename = "_".join([prefix, source.get("type"), source.get("name"), ".csv"])
            filepath = os.path.join(
                dirname, filename
            )
            df.to_csv(filepath)
            logger.info("Saving series data to %s", filepath)

        return metrics_summary

    def _extract_evals(self, evals, prefix, test, trial, snap_role, save=False):
        metrics = {
            "test": test,
            "trial": trial,
        }
        
        general_metrics = {}
        for ev in evals:
            ev_metrics_source = ev.get("source")
            ev_metrics = ev.get("metrics")

            metrics_summary = {}
            if type(ev_metrics) is list:

                metrics_summary = { metric.get("name"):metric.get("value")
                                    for metric in ev_metrics if not metric.get("series") }

                metrics_series = [ metric for metric in ev_metrics if metric.get("series") ]
                if metrics_series:
                    metrics_series_summary = self._extract_metrics(metrics_series, prefix, ev_metrics_source, save=save)
                    metrics_summary.update(metrics_series_summary)
                            
            general_metrics.update(metrics_summary)

        metrics_frmt = {"metric_" + snap_role + "_" + k:v for k, v in general_metrics.items()}
        metrics.update(metrics_frmt)

        return metrics

    def _extract_snaps(self, snaps, report_id, test, save=False):
        metrics = {} 
        for snap in snaps:
            snap_trial = snap.get("trial")
            snap_origin = snap.get("origin")          
            snap_role = snap_origin.get("role")          
            evals = snap.get("evaluations")
            prefix = "_".join(["report", str(report_id), "test", str(test), "trial", str(snap_trial)])
            evals_metrics = self._extract_evals(evals, prefix, test, snap_trial, snap_role, save=save)
            metrics.update(evals_metrics)
        return metrics

    def _extract_report(self, report, save=False):
        logger.debug("extracting report")
        metrics = {}
        report_id = report.get("id")    
        report_test = report.get("test")       
        report_inputs = report.get("inputs")
        snaps = report.get("snapshots")
              
        if report_inputs:
            inputs_frmt = {"input_" + k: v for k, v in report_inputs.items()}
        else:
            inputs_frmt = {}

        metrics = self._extract_snaps(snaps, report_id, report_test, save=save)
        metrics.update(inputs_frmt)
        return metrics

    def extract(self, dataframe=True, save=False):
        flat_report_metrics = []
        if self.vnfpp:
            reports = self.vnfpp.get("reports")

            flat_report_metrics = []
            for report in reports:
                filtered_report_metrics = self._extract_report(report, save=save)
                flat_report_metrics.append(filtered_report_metrics)
        else:
            logger.info("No vnfbr loaded")

        if dataframe:
            df = pd.DataFrame(flat_report_metrics)
            return df
        else:
            return flat_report_metrics

    def compile(self):
        df = self.extract(save=True)
        dirname = "./csv"
        filename = "_".join(["vnfbr", str(self.id), ".csv"])       
        filepath = os.path.join(
            dirname, filename
        )
        logger.info("Saving vnfbr data to %s", filepath)
        df.to_csv(filepath)

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