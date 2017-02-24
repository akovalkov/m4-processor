import sys
import os
import re
import subprocess
from tempfile import NamedTemporaryFile

from m4_common import Macro, Token

def bad_args(arguments, min = -1, max = -1, exception=True):
	argc = len(arguments)
	name = arguments[0] if argc > 0 else ''
	if min > 0 and argc < min:
		if exception:
			raise Exception("Warning: too few arguments to builtin '%s'" % name)
		else: 
			return False
	elif max > 0  and argc > max:
		if exception:
			raise Exception("Warning: excess arguments to builtin '%s' ignored" % name)
		else: 
			return False
	return True

def m4___file__(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 1)
	current_file = processor.current_file()
	name = current_file.name if current_file else ''
	return processor.config['left_quote'] + name + processor.config['right_quote'] 

def m4___line__(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 1)
	current_file = processor.current_file()
	line = current_file.line if current_file else 0
	return processor.config['left_quote'] + str(line) + processor.config['right_quote'] 

def m4___program__(processor, arguments) :
	processor.debug_builtin_call(arguments)
	raise Exception("Not implemeneted yet")


# change comment delimiters
def m4_changecom(processor, arguments) : 
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 3)
	if len(arguments) > 1:
		processor.config['begin_comment'] = arguments[1]
	if len(arguments) > 2:
		processor.config['end_comment'] = arguments[2]
	processor.debug_output("m4_changecom(%s, %s)" % (processor.config['begin_comment'], processor.config['end_comment']))

# change quote delimiters
def m4_changequote(processor, arguments) : 
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 3)
	if len(arguments) > 1:
		processor.config['left_quote'] = arguments[1]
	if len(arguments) > 2:
		processor.config['right_quote'] = arguments[2]
	processor.debug_output("m4_changequote(%s, %s)" % (processor.config['left_quote'], processor.config['right_quote']))

def m4_debugmode(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 2)
	if len(arguments) > 1:
		processor.set_debug_level(arguments[1])
	else:
		processor.set_debug_level()

def m4_debugfile(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 2)
	if len(arguments) > 1:
		processor.debug_set_output(arguments[1])
	else:
		processor.debug_set_output()

def m4_traceoff(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if num_args == 1:
		processor.set_trace(None, False)
	else:
		for i in range(1, num_args):
			processor.set_trace(arguments[i], False)


def m4_traceon(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if num_args == 1:
		processor.set_trace(None, True)
	else:
		for i in range(1, num_args):
			processor.set_trace(arguments[i], True)


def m4_decr(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2, 2)
	num_value = int(arguments[1])
	num_value -= 1
	return str(num_value)

def m4_incr(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2, 2)
	num_value = int(arguments[1])
	num_value += 1
	return str(num_value)

def define_macro(processor, arguments, mode):
	bad_args(arguments, 2, 3)
	macro_name = arguments[1]

	if len(arguments) == 2:
		processor.define_user_macro(macro_name, "", mode)
		return
	macro_body = arguments[2]
	if callable(macro_body): # builtin macro
		bp = find_builtin_by_addr(macro_body)
		if bp:
			(dummy, gnu_extension, groks_macro_args, blind_if_no_args, func) = bp
			processor.define_builtin(macro_name, func, groks_macro_args, blind_if_no_args, mode)
	else: # text macro
		processor.define_user_macro(macro_name, macro_body, mode)


def m4_define(processor, arguments) :
	processor.debug_builtin_call(arguments)
	define_macro(processor, arguments, 'insert')

def m4_undefine(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	for i in range(1, len(arguments)):
		processor.lookup_macro(arguments[i], 'delete')

def m4_pushdef(processor, arguments) :
	processor.debug_builtin_call(arguments)
	define_macro(processor, arguments, 'pushdef')

def m4_popdef(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	for i in range(1, len(arguments)):
		processor.lookup_macro(arguments[i], 'popdef')

def m4_defn(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	for i in range(1, len(arguments)):
		argument = arguments[1]
		macro = processor.lookup_macro(argument)
		if macro is None:
			continue
		if macro.type == Macro.TOKEN_DATA_TEXT:
			return processor.config['left_quote'] + macro.data + processor.config['right_quote']
		elif macro.type == Macro.TOKEN_DATA_FUNC:
			if macro.data == m4_placeholder:
				raise Exception("builtin '%s' requested by frozen file is not supported" % argument)
			elif len(arguments) != 2:
				raise Exception("Warning: cannot concatenate builtin '%s'" % argument)
			else:
				processor.push_macro(macro.data)
		elif macro.type == Macro.TOKEN_DATA_VOID:	
			break
		else:
			raise Exception("INTERNAL ERROR: bad symbol type in m4_defn ()")
	return None

def m4_divert(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 2)
	divnum = arguments[1] if len(arguments) > 1 else '0'
	processor.make_diversion(divnum) # accept strings

def m4_divnum(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 1)
	return str(processor.current_diversion)

def m4_undivert(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if num_args == 1:
		processor.undivert_all()
	else:
		for i in range(1, num_args):
			processor.undivert(arguments[i])

def m4_dnl(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 1)
	processor.skip_line()

def m4_errprint(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	errmsg = arguments[1]
	sys.stderr.write(errmsg)
	sys.stderr.flush()

def m4_eval(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2, 4)
	eval_str = arguments[1]
	if len(arguments) > 2 and arguments[2]:
		radix = int(arguments[2])
	else:
		radix = 10
	if radix != 10:
		raise Exception("The radix support only 10")

	if len(arguments) > 3 and arguments[3]:
		min = int(arguments[3])
	else:
		min = 1
	# prepare eval_str
	eval_str = eval_str.replace('||', ' or ')
	eval_str = eval_str.replace('&&', ' and ')
	eval_str = eval_str.replace('!', 'not ')
	# eval 
	processor.debug_output("EVAL: %s" % eval_str)
	result = eval(eval_str)
	return "%d" % result

def m4_format(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	format_str = arguments[1]
	# convert values to format type
	pattern = r"%['+\- 0#*\.*hhd]*[csdioxXuaAeEfFgG]"
	values = list(arguments[2:])
	for i,match in enumerate(re.finditer(pattern, format_str)):
		format_type = match.group(0)[-1]
		if format_type == 'c' or format_type in "dioxXu":
			values[i] = int(values[i])
		elif format_type in "AeEfFgG":
			values[i] = float(values[i])
	return format_str % tuple(values)

def m4_ifdef(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 3, 4)
	symbol = arguments[1]
	# symbol is defined
	if processor.find_macro_by_name(symbol):
		result = arguments[2]
	elif len(arguments) > 3:
		result = arguments[3]
	else:
		result = None
	return result	

def m4_ifelse(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_arguments = len(arguments) 
	if num_arguments == 2:
		return None
	bad_args(arguments, 4)
	#  Diagnose excess arguments if 5, 8, 11, etc., actual arguments. 
	if (num_arguments + 2) % 3 > 1:
		raise Exception("Warning: excess arguments to builtin 'm4_ifelse' ignored")

	arg = 1
	result = None
	while result is None:
		if arguments[arg] == arguments[arg + 1]:
			result = arguments[arg + 2]
		else:
			num_args = len(arguments) - arg
			if num_args == 3:
				return None
			elif num_args == 4 or num_args == 5:
				result = arguments[arg + 3]
				break
			else:
				arg += 3

	return result

def include(processor, arguments, silent):
	bad_args(arguments, 2, 2)
	filename = arguments[1]
	filepath = processor.search_file(filename)
	if filepath is None:
		if not silent:
			raise Exception("cannot open '%s'" % filename)
		return None
	processor.push_file(filename, filepath)

# Include a file, complaining in case of errors.
def m4_include(processor, arguments) :
	processor.debug_builtin_call(arguments)
	include(processor, arguments, False)

# Include a file, ignoring errors. 
def m4_sinclude(processor, arguments) :
	processor.debug_builtin_call(arguments)
	include(processor, arguments, True)

def m4_indir(processor, arguments) : # indirect execute macro
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	name = arguments[1]
	macro = processor.lookup_macro(name)
	if macro is None or macro.type == Macro.TOKEN_DATA_VOID:
		raise Exception("Undefined macro '%s'" % name)
	sub_arguments = list(arguments[1:])
	if hasattr(macro, 'blind_no_args') and not macro.blind_no_args:
		for i in range(1, len(sub_arguments)):
			if not isinstance(sub_arguments[i], (str, unicode)):
				sub_arguments[i] = ""
	return processor.call_macro(macro, tuple(sub_arguments))

# The builtin "builtin" allows calls to builtin macros, even if    
# their definition has been overridden or shadowed.  It is thus    
# possible to redefine builtins, and still access their original   
# definition.  This macro is not available in compatibility mode.  
def m4_builtin(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	name = arguments[1]
	bp = find_builtin_by_name(name)
	if bp is None:
		raise Exception("Warning: %s: invalid macro name ignored" % name)
	(name, gnu_extension, groks_macro_args, blind_if_no_args, func) = bp
	sub_arguments = list(arguments[1:])
	if not groks_macro_args:
		for i in range(1, len(sub_arguments)):
			if not isinstance(sub_arguments[i], (str, unicode)):
				sub_arguments[i] = ""
	func(processor, sub_arguments)

def m4_index(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 3, 3)
	haystack = arguments[1]
	string = arguments[2] 
	result = string.find(haystack)
	return str(result)

def m4_len(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2, 2)
	length = len(arguments[1])
	return str(length)

def m4_substr(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if not bad_args(arguments, 3, 4, False):
		if num_args == 2:
			# builtin(`substr') is blank, but substr(`abc') is abc. 
			return argument[1]
	string = argument[1]
	start = int(argument[2])
	if start < 0 or start >= len(string):
		return
	if num_args > 3:
		length = int(argument[3])
		if length <= 0 or start + length >= len(string):
			return
		end = start + length
		return string[start:end]
	else:
		return string[start:]

def m4_m4exit(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 1, 2)
	exitcode = 0
	if len(arguments) > 1:
		exitcode = arguments[1]
	processor.debug_output("m4_m4exit(%s)" % exitcode)
	sys.stdout.flush()
	sys.stderr.flush()
	sys.exit(exitcode)

def normalize_regexp(regexp):
	regexp = regexp.replace(r'\(', '(')
	regexp = regexp.replace(r'\)', ')')
	regexp = regexp.replace(r'\{', '{')
	regexp = regexp.replace(r'\}', '}')
	return regexp

def substitute(processor, text, repl, match):
	result = ''
	offset = 0
	while True:
		index  = repl.find('\\', offset)
		if index == -1:
			result += repl[offset:]
			return result
		result += repl[offset : index]
		index += 1
		if index < len(repl) and (repl[index].isdigit() or repl[index] == '&'):
			if repl[index] == '&': # analog '\0'
				i = 0
			else:
				i = int(repl[index])
			if i < len(match.groups()) + 1:
				result += text[match.start(i):match.end(i)]
			offset = index + 1 
		else:
			result += '\\'
			offset = index

def m4_patsubst(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if not bad_args(arguments, 3, 4, False):
		# builtin(`patsubst') is blank, but patsubst(`abc') is abc. 
		if num_args == 2:
			return arguments[1]
	text = arguments[1]
	regexp = normalize_regexp(arguments[2])
	repl = arguments[3] if num_args > 3 else ''
	pattern = re.compile(regexp)
	result = ''
	offset = 0
	for match in pattern.finditer(text):
		result += text[offset:match.start()]
		result += substitute(processor, text, repl, match)
		offset = match.end()
	result += text[offset:]
	return result

def m4_regexp(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if not bad_args(arguments, 3, 4, False):
		# builtin(`regexp') is blank, but regexp(`abc') is 0.
		if num_args == 2:
			return str(0)
	text = arguments[1]
	regexp = normalize_regexp(arguments[2])
	pattern = re.compile(regexp)
	match = pattern.search(text)
	if match:
		if num_args == 3:
			return str(match.start())
		else:
			repl = arguments[3]
			return substitute(processor, text, repl, match)

def m4_shift(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	return processor.dump_args(arguments[1:], True)

def expand_ranges(string):
	from_symbol = None
	to_symbol = None

	result = ''
	i = 0
	for i in range(len(string)):
		symbol = string[i]
		if symbol == '-' and from_symbol is not None:
			to_symbol = string[i + 1] if i < len(string) - 1 else None
			if to_symbol is None:
				# trailing dash
				result += symbol
				break
			elif ord(from_symbol) <= ord(to_symbol):
				from_ord = ord(from_symbol) + 1
				to_ord = ord(to_symbol)
				while from_ord < to_ord:
					result += chr(from_ord)
					from_ord += 1
			else:
				from_ord = ord(from_symbol) - 1
				to_ord = ord(to_symbol)
				while from_ord >= to_ord:
					result += chr(from_ord)
					from_ord -= 1

		else:
			result += symbol
			from_symbol = symbol
	return result


def m4_translit(processor, arguments) :
	processor.debug_builtin_call(arguments)
	if not bad_args(arguments, 3, 4, False):
		#  builtin(`translit') is blank, but translit(`abc') is abc.
		if len(arguments) <= 2:
			return arguments[1]
		else:
			return None
	data = arguments[1]
	from_str = arguments[2]
	to_str = arguments[3] if len(arguments) > 3 else '' 

	if to_str.find('-') != -1:
		to_str = expand_ranges(to_str)
	if from_str.find('-') != -1:
		from_str = expand_ranges(from_str)

	translit_map = {}
	j = 0
	for i in range(len(from_str)):
		if from_str[i] not in translit_map:
			translit_map[from_str[i]] = to_str[j] if j < len(to_str) else ''
		if j < len(to_str):
			j += 1	

	result = ''
	for symbol in data:
		if symbol in translit_map:
			result += translit_map[symbol]
		else:
			result += symbol
	return result

def m4_dumpdef(processor, arguments) :
	processor.debug_builtin_call(arguments)
	num_args = len(arguments)
	if num_args == 1:
		processor.dump_all_macros()
	else:
		for i in range(1, num_args):
			processor.dump_macro(arguments[i])

def m4_m4wrap(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2)
	if processor.config['no_gnu_extensions']:
		return arguments[1]
	else:
		return  processor.dump_args(arguments[1:], False, ' ')


def m4_esyscmd(processor, arguments) :
	processor.debug_builtin_call(arguments)
	if not bad_args(arguments, 2, 2, False):
		#  The empty command is successful.
		processor.returncode = 0
		return
	try:
		# original version of the 'esyscmd', it doesn't return error in stdout
		# processor.returncode = subprocess.check_output(arguments[1], shell=True)
		output = subprocess.check_output(arguments[1], stderr=subprocess.STDOUT, shell=True)
		processor.returncode = 0
	except subprocess.CalledProcessError as e:
		processor.returncode = e.returncode
		output = e.output
	return output

def m4_syscmd(processor, arguments) :
	processor.debug_builtin_call(arguments)
	if not bad_args(arguments, 2, 2, False):
		#  The empty command is successful.
		processor.returncode = 0
		return
	try:
		processor.returncode = subprocess.check_call(arguments[1], shell=True)
	except subprocess.CalledProcessError as e:
		processor.returncode = e.returncode

def m4_sysval(processor, arguments) :
	processor.debug_builtin_call(arguments)
	return str(processor.returncode)

def mkstemp_helper(processor, macro_name, pattern):
	pattern = pattern.rstrip('X')
	return processor.config['left_quote'] + NamedTemporaryFile(prefix=pattern).name + processor.config['right_quote']

def m4_maketemp(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2, 2)
	return mkstemp_helper(processor, arguments[0], arguments[1])

def m4_mkstemp(processor, arguments) :
	processor.debug_builtin_call(arguments)
	bad_args(arguments, 2, 2)
	return mkstemp_helper(processor, arguments[0], arguments[1])

def m4_placeholder(processor, arguments) :
	processor.debug_builtin_call(arguments)
	raise Exception("Not implemeneted yet")

builtin_tab = [
  # name               GNUext  macros  blind   function 
  ( "__file__",         True,   False,  False,  m4___file__ ),
  ( "__line__",         True,   False,  False,  m4___line__ ),
  ( "__program__",      True,   False,  False,  m4___program__ ),
  ( "builtin",          True,   True,   True,   m4_builtin ),
  ( "changecom",        False,  False,  False,  m4_changecom ),
  ( "changequote",      False,  False,  False,  m4_changequote ),
  ( "debugmode",        True,   False,  False,  m4_debugmode ),
  ( "debugfile",        True,   False,  False,  m4_debugfile ),
  ( "decr",             False,  False,  True,   m4_decr ),
  ( "define",           False,  True,   True,   m4_define ),
  ( "defn",             False,  False,  True,   m4_defn ),
  ( "divert",           False,  False,  False,  m4_divert ),
  ( "divnum",           False,  False,  False,  m4_divnum ),
  ( "dnl",              False,  False,  False,  m4_dnl ),
  ( "dumpdef",          False,  False,  False,  m4_dumpdef ),
  ( "errprint",         False,  False,  True,   m4_errprint ),
  ( "esyscmd",          True,   False,  True,   m4_esyscmd ),
  ( "eval",             False,  False,  True,   m4_eval ),
  ( "format",           True,   False,  True,   m4_format ),
  ( "ifdef",            False,  False,  True,   m4_ifdef ),
  ( "ifelse",           False,  False,  True,   m4_ifelse ),
  ( "include",          False,  False,  True,   m4_include ),
  ( "incr",             False,  False,  True,   m4_incr ),
  ( "index",            False,  False,  True,   m4_index ),
  ( "indir",            True,   True,   True,   m4_indir ),
  ( "len",              False,  False,  True,   m4_len ),
  ( "m4exit",           False,  False,  False,  m4_m4exit ),
  ( "m4wrap",           False,  False,  True,   m4_m4wrap ),
  ( "maketemp",         False,  False,  True,   m4_maketemp ),
  ( "mkstemp",          False,  False,  True,   m4_mkstemp ),
  ( "patsubst",         True,   False,  True,   m4_patsubst ),
  ( "popdef",           False,  False,  True,   m4_popdef ),
  ( "pushdef",          False,  True,   True,   m4_pushdef ),
  ( "regexp",           True,   False,  True,   m4_regexp ),
  ( "shift",            False,  False,  True,   m4_shift ),
  ( "sinclude",         False,  False,  True,   m4_sinclude ),
  ( "substr",           False,  False,  True,   m4_substr ),
  ( "syscmd",           False,  False,  True,   m4_syscmd ),
  ( "sysval",           False,  False,  False,  m4_sysval ),
  ( "traceoff",         False,  False,  False,  m4_traceoff ),
  ( "traceon",          False,  False,  False,  m4_traceon ),
  ( "translit",         False,  False,  True,   m4_translit ),
  ( "undefine",         False,  False,  True,   m4_undefine ),
  ( "undivert",         False,  False,  False,  m4_undivert ),
  ( "placeholder",      True,   False,  False,  m4_placeholder )
]

predefined_tab = [

  ("unix",     "__unix__",   ""),
  ("windows", "__windows__", ""),
  (None,      "__gnu__",     "")
]

def find_builtin_by_name(func_name):
	for i, (name, gnu_extension, groks_macro_args, blind_if_no_args, func) in enumerate(builtin_tab):
		if name == func_name:
			return builtin_tab[i]	
	return None

def find_builtin_by_addr(func_addr):
	for i, (name, gnu_extension, groks_macro_args, blind_if_no_args, func) in enumerate(builtin_tab):
		if func_addr == func:
			return builtin_tab[i]	
	return None


def builtin_init(processor, no_gnu_extensions = False, prefix_all_builtins = False):
	# builtin
	for name, gnu_extension, groks_macro_args, blind_if_no_args, func in builtin_tab:
		if no_gnu_extensions and gnu_extension:
			continue
		if prefix_all_builtins:
			name = "m4_" + name
		processor.define_builtin(name, func, groks_macro_args, blind_if_no_args)
	# defines
	for unix_name, gnu_name, func in predefined_tab:
		if no_gnu_extensions:
			if unix_name:
				processor.define_user_macro(unix_name, func)
		else:
			if gnu_name:
				processor.define_user_macro(gnu_name, func)


