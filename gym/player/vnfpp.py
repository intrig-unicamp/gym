import logging
logger = logging.getLogger(__name__)

import os
from functools import reduce

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from gym.common.info import Content


class VNFPP(Content):
    def __init__(self):
        Content.__init__(self)
        self.id = None
        self.reports = []
        self._inputs_list = {}
        self._instance = None
        self._reports = {}
        self._vnfbd_instances_inputs = {}
        
    def set_id(self, instance_id):
        self.id = instance_id
    
    def get_id(self):
        return self.id

    def add_report(self, vnfbd, report):
        report_id = report.get_id()
        self._reports[report_id] = report
        self._vnfbd_instances_inputs[report_id] = vnfbd.get_inputs()

    def _retrieve_dict(self, content, keywords):
        _dict = {}
        for key in keywords:
            value = content.get(key)
            _dict[key] = value
        return _dict

    def _process_evaluation(self, evaluation):
        keywords = ['id', 'source', 'metrics', 'timestamp']
        eval = self._retrieve_dict(evaluation, keywords)
        return eval

    def _process_snapshot(self, snapshot):
        keywords = ['id', 'trial', 'origin', 'timestamp']
        evaluations = snapshot.get('evaluations')
        evals = list(map(self._process_evaluation, evaluations))
        snap = self._retrieve_dict(snapshot, keywords)
        snap['evaluations'] = evals
        return snap

    def _filter_vnfbd_inputs(self, vnfbd_inputs):
        filtered_inputs = {}

        for inputs_list in self._inputs_list:
            path = inputs_list[:-1]
            input_value = reduce(dict.__getitem__, path, vnfbd_inputs)
            input_name = '_'.join(path)
            filtered_inputs[input_name] = input_value

        logger.debug("report filtered_inputs %s", filtered_inputs)
        return filtered_inputs

    def compile(self, layout_id=None):
        logger.info("compile vnf-pp")
        self._instance = layout_id
        for report_id,report in self._reports.items(): 
            snapshots = report.get('snapshots')
            snaps = list(map(self._process_snapshot, snapshots))
            keywords = ['id', 'test', 'timestamp']
            profile = self._retrieve_dict(report, keywords)
            profile['snapshots'] = snaps
            vnfbd_inputs = self._vnfbd_instances_inputs.get(report_id)
            profile_inputs = self._filter_vnfbd_inputs(vnfbd_inputs)
            profile['inputs'] = profile_inputs
            self.reports.append(profile)

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
        logger.info("vnf-pp parse_inputs")
        lists_paths = self.lists_paths(inputs)
        logger.info("lists_paths %s", lists_paths)
        self._inputs_list = lists_paths