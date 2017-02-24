
class Macro(object):
    # The data for a token, a macro argument, and a macro definition.
    TOKEN_DATA_VOID = 10
    TOKEN_DATA_TEXT = 11
    TOKEN_DATA_FUNC = 12

    def __init__(self):
        self.type = self.TOKEN_DATA_VOID
        self.data = None
        self.name = ''
        self.help = ''
        self.pending_expansions = 0
        self.traced = False

    def call(self, processor, args):
        if self.type != self.TOKEN_DATA_FUNC:
            raise Exception("Macro '%s' isn't function " % self.name)
        return self.data(processor, args)

class Token(object):
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


class Block(object):
    INPUT_STRING = 0    # String resulting from macro expansion.
    INPUT_FILE = 1      # File from command line or include.
    INPUT_MACRO = 2     # Builtin resulting from defn.

    CHAR_EOF = "-1"   # character return on EOF 
    CHAR_MACRO = "-2" # character return for MACRO token 

    def __init__(self, type, arg1, arg2 = None):
        self.type = type
        self.line = 1
        self.offset = 0
        self.start_of_input_line = False
        if type == self.INPUT_FILE:
            self.name = arg1
            self.content = self.read_file(arg2)
        elif type == self.INPUT_STRING:
            self.name = None
            self.content = arg1
        elif type == self.INPUT_MACRO:
            self.name = None
            self.content = arg1
        else:
            raise Exception("Unknown input block type %d" % type)

    def read_file(self, filepath):
        return open(filepath).read()

    def next_symbol(self):
        # check new line start
        if self.type == self.INPUT_FILE and self.start_of_input_line:
            self.start_of_input_line = False
            self.line += 1 # track line number only for file
            #print("line: %d" % self.line)
        # check end of content
        if self.offset >= len(self.content):
            return self.CHAR_EOF
        symbol = self.content[self.offset]
        if self.type == self.INPUT_FILE and symbol == '\n': # next symbol start a new line
            self.start_of_input_line = True
        self.offset += 1
        return symbol   

    def peek_symbol(self, shift = 0):
        if self.offset + shift >= len(self.content):
            return self.CHAR_EOF
        return self.content[self.offset + shift]

    def __str__(self):
        types = ['INPUT_STRING','INPUT_FILE','INPUT_MACRO']
        if self.name:
            return "%s name %s line %d" % (types[self.type - self.INPUT_STRING], self.name, self.line)
        else:
            return "%s line %d" % (types[self.type - self.INPUT_STRING], self.line)

