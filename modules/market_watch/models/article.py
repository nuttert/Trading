import json

class Article:
    def __init__(self, text, info=None):
        self._text = text.replace("'","\"") if text else None
        self._info = info
    
    def get_text(self):
        return self._text

    def get_info(self):
        return self._info

    def set_info(self, info):
        self._info = info

    def __str__(self):
        dict_res = {
            "info": str(self._info),
            "text": self._text[:50]+"...",
        }
        return json.dumps(dict_res)

    def get_dict(self):
        dict_res = {
            **self._info.get_dict(),
            "text": "'{}'".format(self._text) if self._text else "null",
        }
        return dict_res