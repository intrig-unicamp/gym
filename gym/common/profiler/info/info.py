import json


class Info:
    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.info = {}

    def profile(self):
        self.extract_info()
        self.info["id"] = self.id
        self.info["name"] = self.name
        return self.to_json(value=self.info)

    def items(self, dic=False):
        if dic:
            return dict([(i, self.__dict__[i]) for i in self.__dict__.keys() if i[:1] != '_'])
        else:
            return [i for i in self.__dict__.keys() if i[:1] != '_']

    def to_json(self, value=None):
        if value:
            return json.dumps(value, default=lambda o: o.__dict__,
                              sort_keys=True, indent=4)
        return json.dumps(self.items(dic=True), default=lambda o: o.__dict__,
                          sort_keys=True, indent=4)

    def extract_info(self):
        raise NotImplementedError