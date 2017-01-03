import sys
import os
import argparse

from m4_common import Macro, Token
from m4_builtin import builtin_init, define_builtin, find_builtin_by_addr

class Block:
	INPUT_STRING = 0	# String resulting from macro expansion.
	INPUT_FILE = 1		# File from command line or include.
	INPUT_MACRO = 2		# Builtin resulting from defn.

	CHAR_EOF = "-1"   # character return on EOF 
	CHAR_MACRO = "-2" # character return for MACRO token 

	def __init__(self, type, arg):
		self.type = type
		self.line = 0
		self.offset = 0
		self.start_of_input_line = False
		if type == self.INPUT_FILE:
			self.name = os.path.basename(arg)
			self.content = self.read_file(arg)
		elif type == self.INPUT_STRING:
			self.name = None
			self.content = arg
		elif type == self.INPUT_MACRO:
			self.name = None
			self.content = arg
		else:
			raise Exception("Unknown input block type %d" % type)

	def read_file(self, filepath):
		return open(filepath).read()

	def next_symbol(self):
		# check new line start
		if self.start_of_input_line:
			self.start_of_input_line = False
			self.line += 1
			print("line: %d" % self.line)
		# check end of content
		if self.offset >= len(self.content):
			return self.CHAR_EOF
		symbol = self.content[self.offset]
		if symbol == '\n': # next symbol start a new line
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

class M4Parser:
	DEF_LQUOTE = "`"
	DEF_RQUOTE = "\'"
	DEF_BCOMM = "#"
	DEF_ECOMM = "\n"
	
	def __init__(self, config = {}):
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
		self.output_current_line = 0
		# Current recursion level in expand_macro ()
		self.expansion_level = 0
		# The number of the current call of expand_macro ().
		self.macro_call_id = 0
		# debug, trace
		self.debug = True
		self.trace = True
		# Init builtin macros
		self.init_buitlin()
	
	def init_buitlin(self):
		self.macrotab = builtin_init(self.config['no_gnu_extensions'], 
									 self.config['prefix_all_builtins'])

	def find_macro_by_name(self, name):
		if name in self.macrotab and len(self.macrotab[name]) > 0:
			macro = self.macrotab[name][0]
			if macro.type == Macro.TOKEN_DATA_TEXT:
				return macro
			elif macro.type == Macro.TOKEN_DATA_FUNC:
				if macro.blind_no_args:
					(next_token, line) = self.peek_token()
					if next_token.type != Token.TOKEN_OPEN:
						return None
				return macro
		return None


	def debug_output(self, msg):
		if not self.debug:
			return
		print(msg)

	def push_file(self, filename):
		block = Block(Block.INPUT_FILE, filename)
		self.stack.append(block) 

	def push_string(self, string):
		block = Block(Block.INPUT_STRING, string)
		self.stack.append(block) 

	def push_macro(self, func):
		block = Block(Block.INPUT_MACRO, func)
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
		self.debug_output("peek_token -> %s" % str(token));
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
						raise Exception("Unexpected '%s' file end at line %s in comment" % (block.name, block.line))
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
								raise Exception("Unexpected '%s' file end at line %s in quoted string" % (block.name, block.line))
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
		self.push_file(filepath)
		while True:
			(token, line) = self.next_token()
			if token.type == Token.TOKEN_EOF:
				break
			self.expand_token(token, line)

	def expand_token(self, token, line, prev_text = None):
		if token.type in [Token.TOKEN_EOF, Token.TOKEN_MACDEF]:
			return None # nothing to do
		elif token.type in [Token.TOKEN_OPEN, Token.TOKEN_COMMA, 
						Token.TOKEN_CLOSE, Token.TOKEN_SIMPLE, Token.TOKEN_STRING]:
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
		if prev_text is not None: # compose text without output
			return prev_text + text
		if not self.config['sync_output']:
			sys.stdout.write(text)
			sys.stdout.flush()
			return None
		if self.start_of_output_line:
			self.start_of_output_line = False
			self.output_current_line += 1

			if self.output_current_line != line:
				sys.stdout.write("#line \"%d\"\n" % line)
				self.output_current_line = line
		
		for symbol in text:
			if self.output_current_line:
				self.output_current_line = False
				self.output_current_line += 1
			if symbol == '\n':
				self.output_current_line = True
			sys.stdout.write(symbol)
		sys.stdout.flush()
		return None

	def expand_macro(self, macro):
		block = self.current_block()
		current_filename = block.name
		current_line = block.line

		macro.pending_expansions += 1
		self.expansion_level += 1
		if self.expansion_level > self.config['nesting_limit']:
			raise Exception("Recursion limit of %d exceeded" % self.config['nesting_limit'])
		self.macro_call_id += 1
		my_call_id = self.macro_call_id

		arguments = self.collect_arguments(macro.name)
		result = self.call_macro(macro, arguments)
		if result:
			self.push_string(result)
		self.expansion_level -= 1
		macro.pending_expansions -= 1

	def collect_arguments(self, name):
		arguments = [name] # macro name always as first argument
		(next_token, line) = self.peek_token()
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
			index  = text.find('$', offset)
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

	def dump_args(self, arguments, quoted, sep = ','):
		real_arguments = arguments[1:]
		if quoted:
			return sep.join([self.config['left_quote'] + arg + self.config['right_quote'] for arg in real_arguments])
		else:
			return sep.join(real_arguments)

	def search_file(self, name):
		search_paths = ['.']
		for search_path in search_paths:
			for dir, subdirs, subfiles in os.walk(search_path):
				for subfile in subfiles:
					if name == subfile:
						return os.path.join(dir, subfile)
		return None    	    	

if __name__ == "__main__":

    optParser = argparse.ArgumentParser(description='Parser for M4 macro processor.')

    optParser.add_argument('-s', '--source', default=None, dest='source', help='Source file')
    options = optParser.parse_args()

    if not options.source or not os.path.exists(options.source):
        sys.exit('Please specify source file: -s')

    m4 = M4Parser()
    m4.process_file(options.source)

