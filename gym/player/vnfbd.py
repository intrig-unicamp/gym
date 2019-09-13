import logging
import os
import re
import copy
import yaml
import itertools
from functools import reduce

logger = logging.getLogger(__name__)

from yaml import load
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from jinja2 import Environment, FileSystemLoader

from gym.common.info import Content

ETC_REL_PATH = '../etc/db/vnf-bd/'


class TemplateParser:
    def __init__(self):
        self.tmp_configs = None
        self.inputs_folder = "inputs/"

    def parse(self, folder, filename, inputs):
        inputs = inputs if inputs else {}        
        logger.info("Parsing template %s - %s", folder, filename)
        rendered = self._render_template(filename, folder, inputs)
        rendered_dict = load(rendered, Loader=Loader)
        # logger.debug("Rendered template %s", rendered_dict)
        return rendered_dict

    def load_inputs(self, folder, filename):
        full_path = self._full_path(folder)
        inputs_filename = 'default-' + filename
        inputs_filepath = os.path.join(full_path, self.inputs_folder, inputs_filename)
        logger.debug("loading default inputs %s", inputs_filepath)
        inputs = self.load_file(inputs_filepath)
        return inputs

    def load_file(self, filename):
        data = {}
        try:
            with open(filename, 'r') as f:
                data = load(f, Loader=Loader)
        except Exception as e:
            logger.debug('exception: could not load vnf-bd file %s', e)
        finally:
            return data

    def _full_path(self, temp_dir):
        return os.path.normpath(
            os.path.join(
                os.path.dirname(__file__), temp_dir))

    def _render_template(self, template_file, temp_dir, context):
        j2_tmpl_path = self._full_path(temp_dir)
        j2_env = Environment(loader=FileSystemLoader(j2_tmpl_path))
        j2_tmpl = j2_env.get_template(template_file)
        rendered = j2_tmpl.render(dict(temp_dir=temp_dir, **context))
        return rendered.encode('utf8')


class Scenario(Content):
    def __init__(self):
        Content.__init__(self)
        self.nodes = None
        self.links = None
        self._topology = None
        self._proceedings = None
        
    def _init(self, **kwargs):
        scenario_items = kwargs.get("scenario")
        self._topology = scenario_items
        # logger.info("scenario_items %s", scenario_items)
        _items = ['nodes', 'links']
        if all([True if _item in scenario_items.keys() else False for _item in _items]):
            logger.debug('ok: scenario does contain mandatory fields')
            for _item, _value in scenario_items.items():
                if _item in _items:
                    self.set(_item, _value)
            return True
        else:
            logger.debug('error: scenario does not contain mandatory fields %s', _items)
            return False

    def get(self):
        return self._topology

    def set_proceedings(self, proceedings):
        self._proceedings = proceedings

    def check_nodes(self, structure, type_="agents"):
        available = structure.get(type_, [])
        required = self._proceedings.get(type_, [])
        logger.info("available %s and required %s", available, required)    
        if required:
            req = True
            if len(required) <= len(available):
                ack = True
            else:
                ack = False    
        else:
            req = False
            ack = True
        
        return (req, ack)
    
    def satisfy(self, manager_info):
        logger.debug("vnfbd satisfy manager_info")
        selected_manager_components = None
        req_agents, ack_agents = self.check_nodes(manager_info, type_="agents")
        req_monitors, ack_monitors = self.check_nodes(manager_info, type_="monitors")
        logger.debug("Satisfy req_agents %s and req_monitors %s: available number of: agents %s - monitors %s", 
                    req_agents, req_monitors, ack_agents, ack_monitors)
        if ack_agents and ack_monitors:
            selected_manager_components = self._satisfy_components(manager_info, req_agents, req_monitors)
        return selected_manager_components

    def _satisfy_components(self, availables_manager, req_agents, req_monitors):
        mappings = {}
        if req_agents:
            agents = self._check_components(availables_manager, 'agents')
            if agents:
                mappings['agents'] = agents
            else:
                return None
        if req_monitors:
            monitors = self._check_components(availables_manager, 'monitors')
            if monitors:
                mappings['monitors'] = monitors
            else:
                return None
        # logger.debug('Selected agents %s - monitors %s, ', agents, monitors)
        return mappings
        
    def parse_req_tool_params(self, req_params_ls):
        req_params = { param.get("input"):param.get("value") for param in req_params_ls}
        return req_params

    #Checks if all probers/listeners ids of required agents/monitors are available in some available manager component
    #and returns selected satisfied tools (required tool ids with params)
    def _check_components_params(self, req_component_tools, aval_component_tools):
        if all([True if tool.get("id") in aval_component_tools.keys() else False
                for tool in req_component_tools]):
            logger.info("All component tools id ack")
            ack_req_tools = []
            ack_req_tool_ids = []
            
            for req_tool in req_component_tools:
                aval_tool = aval_component_tools.get(req_tool.get("id"))
                aval_params = aval_tool.get("parameters")
                req_params_ls = req_tool.get("parameters")
                
                req_params = self.parse_req_tool_params(req_params_ls)
                
                logger.info("aval_params %s - req_params %s", aval_params, req_params)
                #Checks if all params in req prober/listener is contained in available tools params
                if all([True if param in aval_params else False for param in req_params.keys()]):            
                    ack_req_tool = {
                        "id":req_tool.get("id"),
                        "name": req_tool.get("name", None),
                        "parameters": req_params,
                    }
                    
                    ack_req_tool_set = [ack_req_tool]
                    req_tool_instances = req_tool.get("instances", 1)
                    if req_tool_instances:
                        ack_req_tool_set = ack_req_tool_set*len(range(int(req_tool_instances)))

                    ack_req_tools.extend(ack_req_tool_set)
                    ack_req_tool_ids.append(req_tool.get("id"))
            
            #Check if all tool ids (all required probers/listeners to run in a agent/monitor) are satisfied
            if all([True if tool.get("id") in ack_req_tool_ids else False for tool in req_component_tools]):
                logger.debug('Available tools (and its params) satisfy required tools (and its params) %s',
                            ack_req_tools)
                return ack_req_tools
        else:
            logger.debug('Available tools (and its params) %s does not satisfy required tools (and its params) %s',
                        aval_component_tools, req_component_tools)
        return None

    def _check_components(self, availables, component_type):
        logger.info("Checking components/tools/params")
        required_components = self._proceedings.get(component_type)
        available_components = availables.get(component_type)
        component_tool_type = 'probers' if component_type == 'agents' else 'listeners'

        selected_ids = {}
        selected_components = {}
        logger.debug('check_components type %s subtype %s',
                     component_type, component_tool_type)
        # logger.debug("required_components %s", required_components)
        # logger.debug("available_components %s", available_components)

        available_components_ids = dict( [ (available_component.get('id'),available_component)  for available_component in available_components ] )
        # logger.info("available_components_ids %s", available_components_ids)
        for required_component in required_components:
            req_id = required_component.get("id")

            #Checks if req_id is already mapped directly to available_id component - i.e., mandatory mapping
            if req_id in available_components_ids:
                available_component = available_components_ids.get(req_id)
                aval_id = req_id
                if req_id not in selected_ids and aval_id not in selected_ids.values():
                    req_component_tools = required_component.get(component_tool_type)
                    aval_component_tools = available_component.get(component_tool_type)

                    ack_req_component_tools = self._check_components_params(req_component_tools, aval_component_tools)
                    # Maps component_id (agent_id or monitor_id) to required tool and its params
                    if ack_req_component_tools:
                        selected_components[req_id] = ack_req_component_tools
                        selected_ids[req_id] = aval_id
                    else:
                        logger.debug('component %s with items %s does not satisfy %s',
                                    available_component, aval_component_tools, req_component_tools)
            else:
                for available_component in available_components:
                    aval_id = available_component.get("id")

                    if req_id not in selected_ids and aval_id not in selected_ids.values():
                        req_component_tools = required_component.get(component_tool_type)
                        aval_component_tools = available_component.get(component_tool_type)

                        ack_req_component_tools = self._check_components_params(req_component_tools, aval_component_tools)
                        if ack_req_component_tools:
                            selected_components[req_id] = ack_req_component_tools
                            selected_ids[req_id] = aval_id
                            break
                        else:
                            logger.debug('component %s with items %s does not satisfy %s',
                                        available_component, aval_component_tools, req_component_tools)

        req_choices = selected_ids.keys()
        if all([True if req.get("id") in req_choices else False for req in required_components]):
            logger.debug("All components, tools, and params - successfully selected")
            return selected_components
        logger.debug("NOT all components, tools, and params - selected")
        return None


class VNFBD(Content):
    def __init__(self):
        Content.__init__(self)
        self.id = None
        self.name = None
        self.description = None
        self.version = None
        self.author = None
        self.experiments = None
        self.environment = None
        self.targets = None
        self.proceedings = None
        self.scenario = Scenario()
        self._test_id = 0
        self._inputs = None
        self._filename = None
        self._etc_folder = ETC_REL_PATH
        self._parser = TemplateParser()
        self._mux_inputs = {}
        self._deployed = False
        self._informed = False
        self._first_input = True
        self._input_ids = None

    def deployed(self):
        return self._deployed

    def ack_deploy(self):
        self._deployed = True

    def info(self):
        return self._informed

    def ack_info(self):
        self._informed = True

    def get_inputs(self):
        return self._inputs

    def get_experiments(self):
        return self.experiments

    def get_trials(self):
        trials = self.experiments.get("trials")
        return trials

    def get_test(self):
        return self._test_id

    def set_test_id(self, test_id):
        self._test_id = test_id

    def set_id(self, instance_id):
        self.id = instance_id
    
    def get_id(self):
        return self.id

    def filename(self):
        return self._filename

    def load(self, filename, inputs=None):
        self._filename = filename
        self._inputs = {} if not inputs else inputs
        ack = self.init(self._inputs)
        return ack

    def init(self, inputs):
        data = self._parse_template(inputs=inputs)
        # data = self._parse_file()
        ack = self._init(**data)
        return ack

    def _parse_template(self, inputs):
        # logger.info("_parse_template %s %s ", self._etc_folder, self._filename)
        etc_folder = self._update_path()
        data = self._parser.parse(etc_folder, self._filename, inputs)
        return data

    def _update_path(self):
        _filepath = os.path.normpath(os.path.join(
            os.path.dirname(__file__),
            self._etc_folder))
        return _filepath

    def _init(self, **kwargs):
        _items = ['id', 'name', 'author', 'version', 'description',
                  'experiments', 'environment', 'targets', 'proceedings']
        if all([True if _item in kwargs.keys() else False for _item in _items]):
            for _item, _value in kwargs.items():
                if _item in _items:
                    self.set(_item, _value)
            
            logger.info('ok: vnf-bd does contain mandatory fields')
            logger.debug('vnf-bd items set: %s', self.keys())

            self.scenario._init(**kwargs)
            self.scenario.set_proceedings(self.proceedings)
            return True
        else:
            logger.info('error: vnf-bd does not contain mandatory fields %s', _items)
            return False

    def satisfy_scenario(self, manager_info):
        mapping_ids = self.scenario.satisfy(manager_info)
        return mapping_ids

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

    def get_lists(self, list_paths):
        full_lists = []
        for list_fields in list_paths:
            lists = list_fields[-1]
            full_lists.append(lists)
        return full_lists

    def set_dict_path(self, unique_input, path, value):
        reduce(dict.__getitem__, path, unique_input).update(value)

    def fill_unique_inputs(self, inputs, list_paths, unique_lists):
        fill_inputs = copy.deepcopy(inputs)
        unique_inputs = []
        for unique_list in unique_lists:
            pos = 0
            for list_fields in list_paths:
                path = list_fields[0:-2]
                value = {list_fields[-2]:unique_list[pos]}
                # print(path, value)
                self.set_dict_path(fill_inputs, path, value)
                # reduce(dict.get, path, unique_input).update(value)
                pos += 1
            # unique_input = dict(fill_inputs.items())
            unique_input = {}
            unique_input = copy.deepcopy(fill_inputs)
            # print(unique_input['sut']['resources'])
            # print(unique_input['settings']['agent_one'])
            unique_inputs.append(unique_input)
        return unique_inputs

    def mix_inputs(self, inputs):
        list_paths = self.lists_paths(inputs)
        if list_paths:
            lists = self.get_lists(list_paths)
            unique_lists = list(itertools.product(*lists))
            # print(unique_lists)
            # print(list_paths)
            unique_inputs = self.fill_unique_inputs(inputs, list_paths, unique_lists)
            return unique_inputs
        else:
            return [inputs]

    def multiplex_inputs(self, inputs, fields_list=None):
        unique_inputs = []
        if not fields_list:
            fields_list = [ field for field,value in inputs.items() if type(value) is list ]
        fmt_inputs = []
        if fields_list:
            field = fields_list.pop()
            values = inputs[field]
            for value in values:
                fmt_input = {}
                fmt_input.update(inputs)
                fmt_input[field] = value
                fmt_inputs.append(fmt_input)
        else:
            fmt_inputs.append(inputs)
        if fields_list:
            for fmt_input in fmt_inputs:
                u_inputs = self.multiplex_inputs(fmt_input, fields_list=fields_list)
                unique_inputs.extend(u_inputs)
        else:
            unique_inputs.extend(fmt_inputs)
        return unique_inputs

    def multiplex_parameters(self, inputs):
        # mux_inputs = self.multiplex_inputs(inputs)
        mux_inputs = self.mix_inputs(inputs)
        logger.debug("Multiplexed vnfbd inputs %s", mux_inputs)
        self._input_ids = 500

        tests = self.experiments.get("tests", 1)
        for _input in mux_inputs:
            for test_id in range(tests):
                _input_test = copy.deepcopy(_input)
                _input_test["test"] = test_id
                self._mux_inputs[self._input_ids] = _input_test
                self._input_ids += 1

        logger.debug("vnf-bd tests %s - total inputs %s", tests, len(self._mux_inputs))
        self._input_ids = 500

    def get_current_input_id(self):
        return self._input_ids

    def has_next_input(self):
        if self._first_input:
            next_input_id = self._input_ids
        else:
            next_input_id = self._input_ids + 1

        if next_input_id in self._mux_inputs:
            return True
        return False

    def next_input(self):
        next_input = {}
        if self._first_input:
            next_input_id = self._input_ids
            self._first_input = False
        else:
            next_input_id = self._input_ids + 1
        
        if next_input_id in self._mux_inputs:
            next_input = self._mux_inputs.get(next_input_id)
            #Defines Id that will be used by vnfbd instance of such current_input
            next_input["id"] = next_input_id
            self._input_ids = next_input_id     
        
        logger.debug("vnf-bd next input %s", next_input)
        logger.info("vnf-bd input id %s - total %s", next_input, len(self._mux_inputs))
        return next_input

    def environment_deploy(self):
        needs_deploy = self.environment.get('deploy')
        return needs_deploy

    def get_deployment(self):
        topology = self.scenario.get()
        entrypoint_plugin = self.environment.get('plugin')
        return entrypoint_plugin, topology