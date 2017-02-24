import sys
import os
import argparse

from m4_common import Macro, Token, Block
from m4_builtin import builtin_init, find_builtin_by_addr


class M4Processor(object):
    DEF_LQUOTE = "`"
    DEF_RQUOTE = "\'"
    DEF_BCOMM = "#"
    DEF_ECOMM = "\n"

    def __init__(self, config={}):
        self.stack = []
        self.config = {'left_quote' : self.DEF_LQUOTE,
                       'right_quote' : self.DEF_RQUOTE,
                       'begin_comment' : self.DEF_BCOMM,
                       'end_comment' : self.DEF_ECOMM,
                       'sync_output' : True,
                       'nesting_limit': 300,
                       'no_gnu_extensions' : False,
                       'prefix_all_builtins' : False}
        self.config.update(config)
        self.start_of_output_line = True
        self.output_current_line = -1
        # Current recursion level in expand_macro ()
        self.expansion_level = 0
        # The number of the current call of expand_macro ().
        self.macro_call_id = 0
        # my debug
        self.debug = False
        # diversions ()
        self.diversions = {}
        self.current_diversion = 0
        # debug stuff
        self.debug_level = 0
        self.debug_file = None
        # esycmd and syscmd
        # Exit code from last "syscmd" command.
        self.returncode = 0
        # doc comments
        self.comments = []
        # Init builtin macros
        self.init_buitlin()

    def init_buitlin(self):
        self.macrostab = {}
        builtin_init(self, self.config['no_gnu_extensions'], \
                           self.config['prefix_all_builtins'])

    def find_macro_by_name(self, name):
        if name in self.macrostab and len(self.macrostab[name]) > 0:
            macro = self.macrostab[name][0]
            if macro.type == Macro.TOKEN_DATA_TEXT:
                return macro
            elif macro.type == Macro.TOKEN_DATA_FUNC:
                if macro.blind_no_args:
                    (next_token, line) = self.peek_token()
                    if next_token.type != Token.TOKEN_OPEN:
                        return None
                return macro
        return None

    def push_file(self, filename, filepath):
        block = Block(Block.INPUT_FILE, filename, filepath)
        self.stack.append(block)

    def push_string(self, string):
        current_block = self.current_block()
        block = Block(Block.INPUT_STRING, string)
        block.line = current_block.line if current_block else 1
        block.name = current_block.name if current_block else None
        self.stack.append(block)

    def push_macro(self, func):
        current_block = self.current_block()
        block = Block(Block.INPUT_MACRO, func)
        block.line = current_block.line
        if current_block.name:
            block.name = current_block.name
        self.stack.append(block)

    def current_block(self):
        return self.stack[-1] if len(self.stack) > 0 else None

    def current_file(self):
        index = len(self.stack) - 1
        while index >= 0 and self.stack[index].name is None:
            index -= 1
        return self.stack[index] if index >= 0 else None

    def pop_input(self):
        if len(self.stack) > 0:
            self.stack.pop()

    def peek_symbol(self):
        while len(self.stack) > 0:
            block = self.current_block()
            if block.type == Block.INPUT_MACRO:
                return Block.CHAR_MACRO
            else: # Block.INPUT_FILE or Block.INPUT_STRING
                symbol = block.peek_symbol()
                if symbol != Block.CHAR_EOF:
                    return symbol
                self.pop_input()
        return Block.CHAR_EOF

    def next_symbol(self):
        while len(self.stack) > 0:
            block = self.current_block()
            if block.type == Block.INPUT_MACRO:
                self.pop_input()
                return Block.CHAR_MACRO
            else: # Block.INPUT_FILE or Block.INPUT_STRING
                symbol = block.next_symbol()
                if symbol == Block.CHAR_EOF:
                    self.pop_input()
                    continue
                else:
                    return symbol
        return Block.CHAR_EOF

    def match_input(self, match, consume):
        data = ''
        for i in range(len(match)):
            # input isn't matched
            symbol = self.peek_symbol()
            if symbol != match[i]:
                if len(data) > 0:
                    # return read data on stack
                    self.push_string(data)
                return None
            data += self.next_symbol()
        # matched
        if not consume:
            # return read data on stack, consume is false
            self.push_string(data)
        return data

    def peek_token(self):
        block = self.current_block()
        # peek symbol
        symbol = self.peek_symbol()
        # end of inputs
        if symbol == Block.CHAR_EOF:
            token = Token(Token.TOKEN_EOF)
        # macro found
        elif symbol == Block.CHAR_MACRO:
            token = Token(Token.TOKEN_MACDEF)
        # comment
        elif self.match_input(self.config['begin_comment'], False):
            token = Token(Token.TOKEN_STRING)
        # word
        elif symbol.isalpha() or symbol == '_':
            token = Token(Token.TOKEN_WORD)
        # quoted string
        elif self.match_input(self.config['left_quote'], False):
            token = Token(Token.TOKEN_STRING)
        # single character
        elif symbol == '(':
            token = Token(Token.TOKEN_OPEN)
        elif symbol == ',':
            token = Token(Token.TOKEN_COMMA)
        elif symbol == ')':
            token = Token(Token.TOKEN_CLOSE)
        else:
            token = Token(Token.TOKEN_SIMPLE)
        self.debug_output("peek_token -> %s" % str(token))
        return (token, block.line if block else 0)

    def next_token(self):
        block = self.current_block()
        # peek symbol
        symbol = self.peek_symbol()
        # end of inputs
        if symbol == Block.CHAR_EOF:
            self.debug_output("next_token -> EOF")
            self.next_symbol()
            return (Token(Token.TOKEN_EOF), block.line if block else 0)
        # macro found
        if symbol == Block.CHAR_MACRO:
            token = Token(Token.TOKEN_MACDEF)
            # set builtin function address
            token.data_type = Macro.TOKEN_DATA_FUNC
            token.data = self.current_block().content
            self.next_symbol() # popup macro block
            builtin = find_builtin_by_addr(token.data)
            if not builtin:
                raise Exception("Unknown builtin, couldn't find it by address")
            self.debug_output("next_token -> MACDEF (%s)" % builtin[0])
            return (token, block.line if block else 0)
        # comment
        token_data = self.match_input(self.config['begin_comment'], True)
        if token_data:
            # read whole comment
            while True:
                end_data = self.match_input(self.config['end_comment'], True)
                if not end_data:
                    # not end yet, read next symbol
                    next_symbol = self.next_symbol()
                    if next_symbol == Block.CHAR_EOF:
                        raise Exception("Unexpected '%s' file end at line %s in comment" \
                                        % (block.name, block.line))
                    token_data += next_symbol
                    continue
                # comment end is reached
                token_data += end_data
                token_type = Token.TOKEN_STRING
                break
        # word
        elif symbol.isalpha() or symbol == '_':
            token_data = ''
            # read whole word (identifier)
            while True:
                token_data += self.next_symbol()
                next_symbol = self.peek_symbol()
                if not next_symbol.isalnum() and next_symbol != '_':
                    break
            token_type = Token.TOKEN_WORD
        else:
        # quote	string
            token_data = self.match_input(self.config['left_quote'], True)
            if token_data:
                token_data = ''
                quote_level = 1
                while True:
                    right_quote_data = self.match_input(self.config['right_quote'], True)
                    if right_quote_data:
                        # right quote was found
                        quote_level -= 1
                        if quote_level == 0:
                            break
                        token_data += right_quote_data
                    else:
                        left_quote_data = self.match_input(self.config['left_quote'], True)
                        # nested quoted string
                        if left_quote_data:
                            quote_level += 1
                            token_data += left_quote_data
                        # still in quoted string
                        else:
                            next_symbol = self.next_symbol()
                            if next_symbol == Block.CHAR_EOF:
                                raise Exception(
                                    "Unexpected '%s' file end at line %s in quoted string" \
                                            % (block.name, block.line))
                            token_data += next_symbol
                # quoted string end is reached
                #token_data += right_quote_data
                token_type = Token.TOKEN_STRING
            # single symbol
            else:
                token_data = self.next_symbol()
                if symbol == '(':
                    token_type = Token.TOKEN_OPEN
                elif symbol == ',':
                    token_type = Token.TOKEN_COMMA
                elif symbol == ')':
                    token_type = Token.TOKEN_CLOSE
                else:
                    token_type = Token.TOKEN_SIMPLE

        token = Token(token_type)
        token.data_type = Macro.TOKEN_DATA_TEXT
        token.data = token_data
        self.debug_output("next_token -> %s" % str(token))
        return (token, block.line if block else 0)

    def skip_line(self):
        block = self.current_block()
        ch = ch = self.next_symbol()
        while ch != Block.CHAR_EOF and ch != '\n':
            ch = self.next_symbol()
        if ch == Block.CHAR_EOF:
            raise Exception('Warning: end of file treated as newline')

    def process_file(self, filename):
        filepath = self.search_file(filename)
        self.push_file(filename, filepath)
        while True:
            (token, line) = self.next_token()
            if token.type == Token.TOKEN_EOF:
                break
            self.expand_token(token, line)

    def expand_token(self, token, line, prev_text=None):
        if token.type in [Token.TOKEN_EOF, Token.TOKEN_MACDEF]:
            return None # nothing to do
        elif token.type in [Token.TOKEN_OPEN, Token.TOKEN_COMMA, \
                        Token.TOKEN_CLOSE, Token.TOKEN_SIMPLE, Token.TOKEN_STRING]:
            # check comment
            if token.type == Token.TOKEN_SIMPLE and token.data == '\n':
                self.comments = []
            elif token.type == Token.TOKEN_STRING and \
                 token.data.startswith(self.config['begin_comment']):
                comment = token.data[
                    len(self.config['begin_comment']) : -len(self.config['end_comment'])]
                self.comments.append(comment)
            return self.shipout_text(token.data, line, prev_text)
        elif token.type == Token.TOKEN_WORD:
            macro = self.find_macro_by_name(token.data)
            if macro:
                self.expand_macro(macro)
                return prev_text
            else:
                return self.shipout_text(token.data, line, prev_text)
        else:
            raise Exception("INTERNAL ERROR: bad token type in expand_token ()")

    def shipout_text(self, text, line, prev_text = None):
        # If output goes to an obstack, merely add TEXT to it.
        if prev_text is not None: # compose text without output
            return prev_text + text
        if self.current_diversion < 0:
            return
        # Do nothing if TEXT should be discarded.
        if not self.config['sync_output']:
            self.output_text(text)
            return None
        if self.start_of_output_line:
            self.start_of_output_line = False
            self.output_current_line += 1

            if self.output_current_line != line:
                line_str = "#line %d" % line
                if self.output_current_line < 1 and self.current_block().name:
                    line_str += " \"%s\"" % self.current_block().name
                line_str += "\n"
                self.output_text(line_str)
                self.output_current_line = line

        for symbol in text:
            if self.start_of_output_line:
                self.start_of_output_line = False
                self.output_current_line += 1
            if symbol == '\n':
                self.start_of_output_line = True
        self.output_text(text)

    def output_text(self, text):
        if self.current_diversion < 0:
            return
        if self.current_diversion == 0:
            sys.stdout.write(text)
            sys.stdout.flush()
            return
        self.diversions[self.current_diversion] += text

    def make_diversion(self, divnum):
        if (divnum[0] == '-' and divnum[1:].isdigit()) or divnum.isdigit():
            divnum = int(divnum)
        if self.current_diversion == divnum:
            return

        self.current_diversion = divnum

        if divnum <= 0:
            return

        if self.current_diversion not in self.diversions:
            self.diversions[self.current_diversion] = ''
        self.start_of_output_line = True
        self.output_current_line = -1

    def undivert_all(self):
        for divnum, text in self.diversions.items():
            if divnum != self.current_diversion:
                self.output_text(text)
                del self.diversions[divnum]

    def undivert(self, divnum):
        if (divnum[0] == '-' and divnum[1:].isdigit()) or divnum.isdigit():
            divnum = int(divnum)
        if divnum in self.diversions:
            self.output_text(self.diversions[divnum])
            del self.diversions[divnum]

    def expand_macro(self, macro):
        block = self.current_block()
        macro.pending_expansions += 1
        self.expansion_level += 1
        if self.expansion_level > self.config['nesting_limit']:
            raise Exception("Recursion limit of %d exceeded" % self.config['nesting_limit'])
        self.macro_call_id += 1
        my_call_id = self.macro_call_id

        traced = (self.debug_level & self.DEBUG_TRACE_ALL) != 0 or macro.traced
        if traced and (self.debug_level & self.DEBUG_TRACE_CALL) != 0:
            self.trace_prepre(macro.name, my_call_id)

        arguments = self.collect_arguments(macro.name)
        if traced:
            self.trace_pre(macro.name, my_call_id, arguments)

        result = self.call_macro(macro, arguments)
        if result:
            self.debug_output("%s => %s" % (macro.name, result))
            self.push_string(result)

        if traced:
            self.trace_post(macro.name, my_call_id, len(arguments), result)

        self.expansion_level -= 1
        macro.pending_expansions -= 1

    def collect_arguments(self, name):
        arguments = [name] # macro name always as first argument
        (next_token, _) = self.peek_token()
        if next_token.type == Token.TOKEN_OPEN:
            self.next_token()
            more_args = True
            while more_args:
                (more_args, argument) = self.expand_argument()
                arguments.append(argument)
        return tuple(arguments)

    def expand_argument(self):
        # skip spaces
        while True:
            (token, current_line) = self.next_token()
            if token.type != Token.TOKEN_SIMPLE or not token.data.isspace():
                break
        argument = ''
        paren_level = 0
        while True:
            if token.type == Token.TOKEN_COMMA:
                if paren_level == 0:
                    return (True, argument)
                argument = self.expand_token(token, current_line, argument)
            elif token.type == Token.TOKEN_CLOSE:
                if paren_level == 0:
                    return (False, argument)
                paren_level -= 1
                argument = self.expand_token(token, current_line, argument)
            elif token.type == Token.TOKEN_OPEN:
                paren_level += 1
                argument = self.expand_token(token, current_line, argument)
            elif token.type == Token.TOKEN_SIMPLE:
                argument = self.expand_token(token, current_line, argument)
            elif token.type == Token.TOKEN_EOF:
                raise Exception("ERROR: end of file in argument list")
            elif token.type in [Token.TOKEN_WORD, Token.TOKEN_STRING]:
                argument = self.expand_token(token, current_line, argument)
            elif token.type == Token.TOKEN_MACDEF:
                argument = token.data
            else:
                raise Exception("INTERNAL ERROR: bad token type in expand_argument ()")
            (token, current_line) = self.next_token()

    def call_macro(self, macro, arguments):
        if macro.type == Macro.TOKEN_DATA_FUNC:
            return macro.call(self, arguments)
        elif macro.type == Macro.TOKEN_DATA_TEXT:
            return self.expand_user_macro(macro, arguments)
        else:
            raise Exception("INTERNAL ERROR: bad macro type in call_macro ()")
        return None

    def expand_user_macro(self, macro, arguments):
        result = ''
        text = macro.data
        offset = 0
        while True:
            index = text.find('$', offset)
            if index == -1:
                result += text[offset:]
                self.debug_output("exapnd_user_macro %s -> %s" % (macro.name, result))
                return result
            result += text[offset : index]
            index += 1
            if text[index].isdigit():
                i = int(text[index])
                while index < len(text) - 1 and text[index + 1].isdigit():
                    index += 1
                    i = 10 * i + int(text[index])
                if i < len(arguments):
                    result += str(arguments[i])
            elif text[index] == '#':
                result += str(len(arguments) - 1)
            elif text[index] == '*':
                result += self.dump_args(arguments, False)
            elif text[index] == '@':
                result += self.dump_args(arguments, True)
            offset = index + 1

    def dump_args(self, arguments, quoted, sep=','):
        real_arguments = arguments[1:]
        if quoted:
            return sep.join([self.config['left_quote'] + arg + \
                   self.config['right_quote'] for arg in real_arguments])
        else:
            return sep.join(real_arguments)

    def search_file(self, filename):
        if os.path.isabs(filename):
            return filename
        if filename[:2] == '.' + os.sep:
            filename = filename[2:]
        search_paths = [os.path.abspath('.')]
        for search_path in search_paths:
            for dir, subdirs, subfiles in os.walk(search_path):
                for subfile in subfiles:
                    absfilepath = os.path.join(dir, subfile)
                    if absfilepath.endswith(filename):
                        return absfilepath
        return None

    def define_user_macro(self, name, text, mode = "insert"):
        macro = Macro()
        macro.name = name
        macro.type = Macro.TOKEN_DATA_TEXT
        macro.data = text
        # add usage help based on comments before macro definition
        if len(self.comments) > 0:
            macro.help = '\n'.join(self.comments)
            self.comments = []
        if mode == "insert":
            self.macrostab[macro.name] = [macro]
        elif mode == "pushdef":
            if macro.name not in self.macrostab:
                self.macrostab[macro.name] = []
            self.macrostab[macro.name].insert(0, macro)
        else:
            raise Exception("Unknown mode '%s' for macro insertion" % mode)

    # mode is INSERT or PUSHDEF
    def define_builtin(self, name, func, groks_macro_args, blind_if_no_args, mode="insert"):
        macro = Macro()
        macro.name = name
        macro.macro_args = groks_macro_args
        macro.blind_no_args = blind_if_no_args
        macro.type = Macro.TOKEN_DATA_FUNC
        macro.data = func
        if mode == "insert":
            self.macrostab[macro.name] = [macro]
        elif mode == "pushdef":
            if macro.name not in self.macrostab:
                self.macrostab[macro.name] = []
            self.macrostab[macro.name].insert(0, macro)
        else:
            raise Exception("Unknown mode '%s' for macro insertion" % mode)


    def lookup_macro(self, name, mode='lookup'):
        if name not in self.macrostab:
            return None
        if mode == 'lookup':
            return self.macrostab[name][0]
        elif mode == 'delete':
            self.macrostab[name].pop(0)
            if len(self.macrostab[name]) == 0:
                del self.macrostab[name]
        elif mode == 'popdef':
            del self.macrostab[name]
        return None

     # debug stuff

    # The value of debug_level is a bitmask of the following.

    # a: show arglist in trace output
    DEBUG_TRACE_ARGS = 1
    # e: show expansion in trace output
    DEBUG_TRACE_EXPANSION = 2
    # q: quote args and expansion in trace output
    DEBUG_TRACE_QUOTE = 4
    # t: trace all macros -- overrides trace{on,off}
    DEBUG_TRACE_ALL = 8
    # l: add line numbers to trace output
    DEBUG_TRACE_LINE = 16
    # f: add file name to trace output
    DEBUG_TRACE_FILE = 32
    # p: trace path search of include files
    DEBUG_TRACE_PATH = 64
    # c: show macro call before args collection
    DEBUG_TRACE_CALL = 128
    # i: trace changes of input files
    DEBUG_TRACE_INPUT = 256
    # x: add call id to trace output
    DEBUG_TRACE_CALLID = 512
    # V: very verbose --  print everything
    DEBUG_TRACE_VERBOSE = 1023
    # default flags -- equiv: aeq
    DEBUG_TRACE_DEFAULT = 7

    def debug_decode(self, opts):
        if opts is None or len(opts) == 0:
            level = self.DEBUG_TRACE_DEFAULT
        else:
            level = 0
            for opt in opts:
                if opt == 'a':
                    level |= self.DEBUG_TRACE_ARGS
                elif opt == 'e':
                    level |= self.DEBUG_TRACE_EXPANSION
                elif opt == 'q':
                    level |= self.DEBUG_TRACE_QUOTE
                elif opt == 't':
                    level |= self.DEBUG_TRACE_ALL
                elif opt == 'l':
                    level |= self.DEBUG_TRACE_LINE
                elif opt == 'f':
                    level |= self.DEBUG_TRACE_FILE
                elif opt == 'p':
                    level |= self.DEBUG_TRACE_PATH
                elif opt == 'c':
                    level |= self.DEBUG_TRACE_CALL
                elif opt == 'i':
                    level |= self.DEBUG_TRACE_INPUT
                elif opt == 'x':
                    level |= self.DEBUG_TRACE_CALLID
                elif opt == 'V':
                    level |= self.DEBUG_TRACE_VERBOSE
                else:
                    return -1
        return level

    def set_debug_level(self, opts = None):
        if opts is None:
            self.debug_level = 0
            return

        if opts[0] == '-' or opts[0] == '+':
            change_flag = opts[0]
            new_debug_level = self.debug_decode(opts[1:])
        else:
            change_flag = 0
            new_debug_level = self.debug_decode(opts)

        if new_debug_level < 0:
            raise Exception("Debugmode: bad debug flags: '%s'" % opts)

        if change_flag == 0:
            self.debug_level = new_debug_level
        elif change_flag == '+':
            self.debug_level |= new_debug_level
        elif change_flag == '-':
            self.debug_level &= ~new_debug_level
        else:
            raise Exception("INTERNAL ERROR: bad flag in m4_debugmode ()")

    def debug_set_output(self, filename = None):
        self.debug_file = filename

    def debug_print(self, msg):
        msg = msg + "\n"
        if self.debug_file is None:
            sys.stderr.write(msg)
            sys.stderr.flush()
        else:
            open(self.debug_file, "a").write(msg)

    def dump_all_macros(self):
        # dump all macros
        for name in sorted(self.macrostab):
            self.dump_macro(name)

    def dump_macro(self, macro_name):
        if macro_name not in self.macrostab:
            return
        macro = self.macrostab[macro_name][0]
        output_str = '%s:\t' % macro.name
        if macro.type == Macro.TOKEN_DATA_TEXT:
            if (self.debug_level & self.DEBUG_TRACE_QUOTE) != 0:
                output_str += '%s%s%s\n' % \
                    (self.config['left_quote'], macro.data, self.config['right_quote'])
            else:
                output_str += '%s\n' % macro.data
        elif macro.type == Macro.TOKEN_DATA_FUNC:
            builtin = find_builtin_by_addr(macro.name)
            if not builtin:
                raise Exception('INTERNAL ERROR: builtin not found in builtin table')
            output_str += '<%s>' % builtin(0) # builtin name
        else:
            raise Exception('INTERNAL ERROR: bad token data type in m4_dumpdef ()')


    def set_trace(self, macro_name, flag):
        if macro_name is None:
            # trace/untrace all macros
            for name, macros in self.macrostab.items():
                macros[0].traced = flag
        elif macro_name in self.macrostab:
            # trace/untrace specific macro
            self.macrostab[macro_name][0].traced = flag

    def trace_header(self, id):
        header_str = 'm4trace:'
        block = self.current_block()
        if block and block.line:
            if block.name and (self.debug_level & self.DEBUG_TRACE_FILE) != 0:
                header_str += '%s:' % block.name
            if (self.debug_level & self.DEBUG_TRACE_LINE) != 0:
                header_str += '%d' % block.line
                header_str += ' -%d- ' % self.expansion_level
            if (self.debug_level & self.DEBUG_TRACE_CALLID) != 0:
                header_str += 'id %d: ' % id
        return header_str

    def trace_prepre(self, name, id):
        output_str = self.trace_header(id)
        output_str += '%s ...' % name
        self.debug_print(output_str)

    def trace_pre(self, name, id, arguments):
        output_str = self.trace_header(id)
        output_str += '%s' % name
        num_args = len(arguments)
        if num_args > 1 and (self.debug_level & self.DEBUG_TRACE_ARGS) != 0:
            output_str += '('
            for i in range(1, num_args):
                if i != 1:
                    output_str += ', '
                if isinstance(arguments[i], (str, unicode)):
                    output_str += '%s%s%s' % \
                        (self.config['left_quote'], arguments[i], self.config['right_quote'])
                else:
                    builtin = find_builtin_by_addr(arguments[i])
                    if not builtin:
                        raise Exception(
                            'INTERNAL ERROR: builtin not found in builtin table! (trace_pre ())')
                    output_str += '<%s>' % builtin(0) # builtin name
            output_str += ')'
        if (self.debug_level & self.DEBUG_TRACE_CALL) != 0:
            output_str += ' -> ???'
            self.debug_print(output_str)

    def trace_post(self, name, id, num_args, expanded):
        output_str = ''
        if (self.debug_level & self.DEBUG_TRACE_CALL) != 0:
            output_str = self.trace_header(id)
            output_str += '%s' % name
            if num_args > 1:
                output_str += '(...)'
        if expanded and (self.debug_level & self.DEBUG_TRACE_EXPANSION) != 0:
            output_str += ' -> %s%s%s' % \
                (self.config['left_quote'], expanded, self.config['right_quote'])
        self.debug_print(output_str)

    # my debug stuff
    def debug_output(self, msg):
        if not self.debug:
            return
        print(msg)

    def debug_builtin_call(self, args):
        if not self.debug:
            return
        name = args[0]
        arguments = args[1:]
        self.debug_output("%s(%s)" % (name, ','.join(map(str, arguments))))

if __name__ == "__main__":

    optParser = argparse.ArgumentParser(description='Parser for M4 macro processor.')

    optParser.add_argument('-s', '--source', default=None, dest='source', help='Source file')
    options = optParser.parse_args()

    if not options.source or not os.path.exists(options.source):
        sys.exit('Please specify source file: -s')

    m4proc = M4Processor()
    m4proc.process_file(options.source)

