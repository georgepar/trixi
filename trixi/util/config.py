#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from trixi.util.util import ModuleMultiTypeDecoder, ModuleMultiTypeEncoder, StringMultiTypeDecoder


class Config(dict):

    def __init__(self, file_=None, config=None, update_from_argv=False, deep=False, **kwargs):

        super(Config, self).__init__()

        # the following allows us to access keys as attributes if syntax permits
        # config["a"] = 1 -> config.a -> 1
        # config["a-b"] = 2 -> config.a-b (not possible)
        # this is purely for convenience
        self.__dict__ = self

        if file_ is not None:
            self.load(file_)

        if config is not None:
            self.update(config, deep)

        self.update(kwargs, deep)
        if update_from_argv:
            update_from_sys_argv(self)

    def update(self, dict_like, deep=False, ignore=None):

        if ignore is None:
            ignore = ()

        if deep:
            self.deepupdate(dict_like, ignore)
        else:
            for key, value in dict_like.items():
                if key in ignore:
                    continue
                if key in self and isinstance(value, dict):
                    self[key].update(value)
                else:
                    self[key] = value

    def deepupdate(self, dict_like, ignore=None):

        def make_mutable(obj, attr, val):
            if isinstance(val, dict):
                obj[attr] = Config()
                for k, v in val.items():
                    make_mutable(obj[attr], k, v)
            elif isinstance(val, list):
                obj[attr] = [None, ] * len(val)
                for i, item in enumerate(val):
                    make_mutable(obj[attr], i, item)
            else:
                obj[attr] = val

        for key, val in dict_like.items():
            if key in ignore:
                continue
            make_mutable(self, key, val)

    def __setattr__(self, key, value):

        if type(value) == dict:
            new_config = Config()
            new_config.update(value)
            super(Config, self).__setattr__(key, new_config)
        else:
            super(Config, self).__setattr__(key, value)

    def __getitem__(self, key):

        if key == "":
            if len(self.keys()) == 1:
                key = list(self.keys())[0]
            else:
                raise KeyError("Empty string only works for single element Configs.")

        if type(key) == str and "." in key:
            superkey = key.split(".")[0]
            subkeys = ".".join(key.split(".")[1:])
            if type(self[superkey]) in (list, tuple):
                try:
                    subkeys = int(subkeys)
                except ValueError:
                    pass
            return self[superkey][subkeys]
        else:
            return super(Config, self).__getitem__(key)

    def __setitem__(self, key, value):

        if key == "":
            if len(self.keys()) == 1:
                key = list(self.keys())[0]
            else:
                raise KeyError("Empty string only works for single element Configs.")

        if type(key) == str and "." in key:
            superkey = key.split(".")[0]
            subkeys = ".".join(key.split(".")[1:])
            if superkey != "" and superkey not in self:
                self[superkey] = Config()
            if type(self[superkey]) == list:
                try:
                    subkeys = int(subkeys)
                except ValueError:
                    pass
            self[superkey][subkeys] = value
        elif type(value) == dict:
            super(Config, self).__setitem__(key, Config(config=value))
        else:
            super(Config, self).__setitem__(key, value)

    def set_with_decode(self, key, value, stringify_value=False):

        if type(key) != str:
            # We could encode the key if it's not a string, but for now raise
            raise TypeError("set_with_decode requires string as key.")
        if type(value) != str:
            raise TypeError("set_with_decode requires string as value.")

        dict_str = ''
        depth = 0
        key_split = key.split(".")

        for k in key_split:
            dict_str += "{"
            dict_str += '"{}":'.format(k)
            depth += 1

        if stringify_value:
            dict_str += '"{}"'.format(value)
        else:
            dict_str += "{}".format(value)

        for _ in range(depth):
            dict_str += "}"

        self.loads(dict_str)

    def set_from_string(self, str_, stringify_value=False):

        key, value = str_.split("=")
        self.set_with_decode(key, value, stringify_value)

    def update_missing(self, dict_like):

        for key, value in dict_like.items():

            if key not in self:
                self[key] = value
            elif isinstance(value, dict):
                self[key].update_missing(value)

    def dump(self, file_, indent=4, separators=(",", ": "), **kwargs):

        if hasattr(file_, "write"):
            json.dump(self, file_,
                      cls=ModuleMultiTypeEncoder,
                      indent=indent,
                      separators=separators,
                      **kwargs)
        else:
            with open(file_, "w") as file_object:
                json.dump(self, file_object,
                          cls=ModuleMultiTypeEncoder,
                          indent=indent,
                          separators=separators,
                          **kwargs)

    def dumps(self, indent=4, separators=(",", ": "), **kwargs):
        return json.dumps(self,
                          cls=ModuleMultiTypeEncoder,
                          indent=indent,
                          separators=separators,
                          **kwargs)

    def load(self, file_, raise_=True, decoder_cls_=ModuleMultiTypeDecoder, **kwargs):

        try:
            if hasattr(file_, "read"):
                new_dict = json.load(file_, cls=decoder_cls_, **kwargs)
            else:
                with open(file_, "r") as file_object:
                    new_dict = json.load(file_object, cls=decoder_cls_, **kwargs)
        except Exception as e:
            if raise_:
                raise e

        self.update(new_dict)

    def loads(self, json_str, **kwargs):

        if not json_str.startswith("{"):
            json_str = "{" + json_str
        if not json_str.endswith("}"):
            json_str = json_str + "}"
        new_dict = json.loads(json_str, cls=ModuleMultiTypeDecoder, **kwargs)
        self.update(new_dict)

    def hasattr_not_none(self, key):
        if key in self:
            if self[key] is not None:
                return True
        return False

    def contains(self, dict_like):
        """Check whether all items in a dictionary-like object match the ones in this ExperimentLogs."""

        dict_like_config = Config(config=dict_like)

        for key, val in dict_like_config.items():

            if key not in self:
                return False
            else:
                if isinstance(val, dict):
                    if not self[key].contains(val):
                        return False
                else:
                    if not self[key] == val:
                        return False

        return True

    @staticmethod
    def init_objects(config):
        """Returns a new ExperimentLogs with types converted to instances.

        Any value that is a ExperimentLogs and contains a type key will be converted to
        an instance of that type::

            {
                "stuff": "also_stuff",
                "convert_me": {
                    type: {
                        "param": 1,
                        "other_param": 2
                    },
                    "something_else": "hopefully_useless"
                }
            }

        becomes::

            {
                "stuff": "also_stuff",
                "convert_me": type(param=1, other_param=2)
            }

        Note that additional entries can be lost as shown above.

        Args:
            config (Config): New ExperimentLogs will be built from this one

        Returns:
            Config: A new config with instances made from type entries.
        """

        def init_sub_objects(objs):
            if isinstance(objs, dict):
                ret_dict = Config()
                for key, val in objs.items():
                    if isinstance(key, type):
                        init_param = init_sub_objects(val)
                        if isinstance(init_param, dict):
                            init_obj = key(**init_param)
                        elif isinstance(init_param, (list, tuple, set)):
                            init_obj = key(*init_param)
                        else:
                            init_obj = key()
                        return init_obj
                    elif isinstance(val, (dict, list, tuple, set)):
                        ret_dict[key] = init_sub_objects(val)
                    else:
                        ret_dict[key] = val
                return ret_dict
            elif isinstance(objs, (list, tuple, set)):
                ret_list = []
                for el in objs:
                    ret_list.append(init_sub_objects(el))
                return ret_list
            else:
                return objs

        return init_sub_objects(config)

    def __str__(self):
        return self.dumps(sort_keys=True)

    def difference_config(self, *other_configs):
        return self.difference_config_static(self, *other_configs)

    @staticmethod
    def difference_config_static(*configs, only_set=False):
        """Make a ExperimentLogs of all elements that differ between N configs.

        The resulting ExperimentLogs looks like this::

            {
                key: (config1[key], config2[key], ...)
            }

        If the key is missing, None will be inserted. The inputs will not be
        modified.

        Args:
            configs (Config): Any number of Configs
            only_set (bool): If only the set of different values hould be returned or for each config the
            corresponding one

        Returns:
            Config: Possibly empty
        """

        difference = dict()
        mmte = ModuleMultiTypeEncoder()

        all_keys = set()
        for config in configs:
            all_keys.update(set(config.keys()))

        for key in all_keys:

            current_values = []
            all_equal = True
            all_configs = True

            for config in configs:

                if key not in config:
                    all_equal = False
                    all_configs = False
                    current_values.append(None)
                else:
                    current_values.append(mmte._encode(config[key]))

                if len(current_values) >= 2:
                    if current_values[-1] != current_values[-2]:
                        all_equal = False

                if type(current_values[-1]) != Config:
                    all_configs = False

            if not all_equal:

                if not all_configs:
                    if not only_set:
                        difference[key] = tuple(current_values)
                    else:
                        difference[key] = tuple(set(current_values))
                else:
                    difference[key] = Config.difference_config_static(*current_values, only_set=only_set)

        return difference

    def flat(self, keep_lists=True, max_split_size=10):
        """Returns a flattened version of the ExperimentLogs as dict.

        Nested Configs and lists will be replaced by concatenated keys like so::

            {
                "a": 1,
                "b": [2, 3],
                "c": {
                    "x": 4,
                    "y": {
                        "z": 5
                    }
                },
                "d": (6, 7)
            }

        Becomes::

            {
                "a": 1,
                "b": [2, 3], # if keep_lists is True
                "b.0": 2,
                "b.1": 3,
                "c.x": 4,
                "c.y.z": 5,
                "d": (6, 7)
            }

        We return a dict because dots are disallowed within ExperimentLogs keys.

        Args:
            keep_lists: Keeps list along with unpacked values
            max_split_size: List longer than this will not be unpacked

        Returns:
            dict: A flattened version of self
        """

        def flat_(obj):
            def items():
                for key, val in obj.items():
                    if isinstance(val, dict) and type(key) == str:
                        intermediate_dict = {}
                        for subkey, subval in flat_(val).items():
                            if type(subkey) == str:
                                yield key + "." + subkey, subval
                            else:
                                intermediate_dict[subkey] = subval
                        if len(intermediate_dict) > 0:
                            yield key, intermediate_dict
                    elif isinstance(val, (list, tuple)):
                        keep_this = keep_lists or type(key) != str
                        if max_split_size not in (None, False) and len(val) > max_split_size:
                            keep_this = True
                        if keep_this:
                            yield key, val
                        if max_split_size in (None, False) or len(val) <= max_split_size:
                            for i, subval in enumerate(val):
                                yield key + "." + str(i), subval
                    else:
                        yield key, val

            return dict(items())

        return flat_(self)

    def to_cmd_args_str(self):
        c_flat = self.flat()

        str_list = []
        for key, val in c_flat.items():

            if isinstance(val, (list, tuple)):
                vals = [str(v) for v in val]
                val_str = " ".join(vals)
            else:
                val_str = str(val)
            str_list.append("--{} {}".format(key, val_str))

        return "  ".join(str_list)


def update_from_sys_argv(config, warn=False):
    import sys
    import argparse
    import warnings

    """Updates the current config with the arguments passed as args when running the programm and removes given
    classes / converts them to None"""

    def str2bool(v):
        if v.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif v.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    if len(sys.argv) > 1:

        parser = argparse.ArgumentParser()
        encoder = ModuleMultiTypeEncoder()
        decoder = ModuleMultiTypeDecoder()

        config_flat = config.flat()
        for key, val in config_flat.items():
            name = "--{}".format(key)
            if val is None:
                parser.add_argument(name)
            else:
                if type(val) == bool:
                    parser.add_argument(name, type=str2bool, default=val)
                elif isinstance(val, (list, tuple)):
                    if len(val) > 0 and type(val[0]) != type:
                        parser.add_argument(name, nargs='+', type=type(val[0]), default=val)
                    else:
                        parser.add_argument(name, nargs='+', default=val)
                else:
                    if type(val) == type:
                        val = encoder._encode(val)
                    parser.add_argument(name, type=type(val), default=val)

        # parse args
        param, unknown = parser.parse_known_args()
        param = vars(param)

        if len(unknown) > 0 and warn:
            warnings.warn("Called with unknown arguments: {}".format(unknown), RuntimeWarning)

        # calc diff between configs
        diff_keys = list(Config.difference_config_static(param, config_flat).keys())

        # convert type args
        ignore_ = []
        for key, val in param.items():
            if val in ("none", "None"):
                param[key] = None
            if type(config_flat[key]) == type:
                if isinstance(val, str):
                    val = val.replace("\'", "")
                    val = val.replace("\"", "")
                param[key] = decoder._decode(val)
            try:
                key_split = key.split(".")
                list_object, _ = ".".join(key_split[:-1]), int(key_split[-1])
                if "--" + list_object in sys.argv:
                    ignore_.append(key)
            except ValueError as ve:
                pass
        for i in ignore_:
            del param[i]

        ### Delete not changed entries
        param_keys = list(param.keys())
        for i in param_keys:
            if i not in diff_keys and i in param:
                del param[i]

        # update dict
        config.update(param)
