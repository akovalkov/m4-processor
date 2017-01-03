
class Macro:
    # The data for a token, a macro argument, and a macro definition.
    TOKEN_DATA_VOID = 10
    TOKEN_DATA_TEXT = 11
    TOKEN_DATA_FUNC = 12

    def __init__(self):
        self.type = self.TOKEN_DATA_VOID
        self.data = None
        self.name = ''
        self.pending_expansions = 0

    def call(self, processor, args):
        if self.type != self.TOKEN_DATA_FUNC:
            raise Exception("Macro '%s' isn't function " % self.name)
        return self.data(processor, args)

class Token:
    # Various different token types.
    TOKEN_EOF = 0     # end of file 
    TOKEN_STRING = 1    # a quoted string or comment 
    TOKEN_WORD = 2    # an identifier 
    TOKEN_OPEN = 3      # ( 
    TOKEN_COMMA = 4   # , 
    TOKEN_CLOSE = 5   # ) 
    TOKEN_SIMPLE = 6  # any other single character
    TOKEN_MACDEF = 7  # a macro's definition (see "defn")

    def __init__(self, type):
        self.type = type
        self.data = None
        self.data_type = Macro.TOKEN_DATA_VOID

    def __str__(self):
        types = ['TOKEN_EOF','TOKEN_STRING', 'TOKEN_WORD','TOKEN_OPEN', 
                 'TOKEN_COMMA', 'TOKEN_CLOSE', 'TOKEN_SIMPLE', 'TOKEN_MACDEF']
        data_types = ['TOKEN_DATA_VOID', 'TOKEN_DATA_TEXT', 'TOKEN_DATA_FUNC']
        if self.data_type == Macro.TOKEN_DATA_FUNC:
            return "%s (%s)" % (types[self.type - self.TOKEN_EOF], data_types[self.data_type - Macro.TOKEN_DATA_VOID])
        elif self.data_type == Macro.TOKEN_DATA_VOID:
            return "%s" % (types[self.type - self.TOKEN_EOF])
        else:
            return "%s (%s)" % (types[self.type - self.TOKEN_EOF], self.data)



