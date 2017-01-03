import sys
import os
import re

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
	bad_args(arguments, 1, 1)
	current_file = processor.current_file()
	name = current_file.name if current_file else ''
	return processor.config['left_quote'] + name + processor.config['right_quote'] 

def m4___line__(processor, arguments) :
	bad_args(arguments, 1, 1)
	current_file = processor.current_file()
	line = current_file.line if current_file else 0
	return processor.config['left_quote'] + str(line) + processor.config['right_quote'] 

def m4___program__(processor, arguments) :
	raise Exception("Not implemeneted yet")


# change comment delimiters
def m4_changecom(processor, arguments) : 
	bad_args(arguments, 1, 3)
	if len(arguments) > 1:
		processor.config['begin_comment'] = arguments[1]
	if len(arguments) > 2:
		processor.config['end_comment'] = arguments[2]
	processor.debug_output("m4_changecom(%s, %s)" % (processor.config['begin_comment'], processor.config['end_comment']))

# change quote delimiters
def m4_changequote(processor, arguments) : 
	bad_args(arguments, 1, 3)
	if len(arguments) > 1:
		processor.config['left_quote'] = arguments[1]
	if len(arguments) > 2:
		processor.config['right_quote'] = arguments[2]
	processor.debug_output("m4_changequote(%s, %s)" % (processor.config['left_quote'], processor.config['right_quote']))

def m4_debugmode(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_debugfile(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_decr(processor, arguments) :
	raise Exception("Not implemeneted yet")

def define_macro(processor, arguments, mode):
	bad_args(arguments, 2, 3)
	macro_name = arguments[1]

	if len(arguments) == 2:
		define_user_macro(processor.macrotab, macro_name, "", mode)
		return
	macro_body = arguments[2]
	if callable(macro_body): # builtin macro
		bp = find_builtin_by_addr(macro_body)
		if bp:
			(dummy, gnu_extension, groks_macro_args, blind_if_no_args, func) = bp
			define_builtin(processor.macrotab, macro_name, func, groks_macro_args, blind_if_no_args, mode)
	else: # text macro
		define_user_macro(processor.macrotab, macro_name, macro_body, mode)


def m4_define(processor, arguments) :
	define_macro(processor, arguments, 'insert')

def m4_undefine(processor, arguments) :
	bad_args(arguments, 2)
	for i in range(1, len(arguments)):
		lookup_macro(processor.macrotab, arguments[i], 'delete')

def m4_pushdef(processor, arguments) :
	define_macro(processor, arguments, 'pushdef')

def m4_popdef(processor, arguments) :
	bad_args(arguments, 2)
	for i in range(1, len(arguments)):
		lookup_macro(processor.macrotab, arguments[i], 'popdef')

def m4_defn(processor, arguments) :
	bad_args(arguments, 2)
	for i in range(1, len(arguments)):
		argument = arguments[1]
		macro = lookup_macro(processor.macrotab, argument)
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
	bad_args(arguments, 2, 2)
	divnum = arguments[1]
	processor.debug_output("m4_changequote(%s)" % divnum)
	if divnum != '-1':
		raise Exception("Not implemeneted yet for divnum %d" % divnum)

def m4_divnum(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_dnl(processor, arguments) :
	bad_args(arguments, 1, 1)
	processor.skip_line()

def m4_dumpdef(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_errprint(processor, arguments) :
	bad_args(arguments, 2)
	errmsg = arguments[1]
	sys.stderr.write(errmsg)
	sys.stderr.flush()

def m4_esyscmd(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_eval(processor, arguments) :
	bad_args(arguments, 2, 4)
	eval_str = arguments[1]
	if len(arguments) > 2:
		radix = int(arguments[2])
	else:
		radix = 10
	if radix != 10:
		raise Exception("The radix support only 10")

	if len(arguments) > 3:
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
	processor.push_file(filepath)

# Include a file, complaining in case of errors.
def m4_include(processor, arguments) :
	include(processor, arguments, False)

# Include a file, ignoring errors. 
def m4_sinclude(processor, arguments) :
	include(processor, arguments, True)

def m4_incr(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_index(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_indir(processor, arguments) : # indirect execute macro
	bad_args(arguments, 2)
	name = arguments[1]
	macro = lookup_macro(processor.macrotab, name)
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


def m4_len(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_m4exit(processor, arguments) :
	bad_args(arguments, 1, 2)
	exitcode = 0
	if len(arguments) > 1:
		exitcode = arguments[1]
	processor.debug_output("m4_m4exit(%s)" % exitcode)
	sys.stdout.flush()
	sys.stderr.flush()
	sys.exit(exitcode)

def m4_m4wrap(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_maketemp(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_mkstemp(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_patsubst(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_regexp(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_shift(processor, arguments) :
	bad_args(arguments, 2)
	return processor.dump_args(arguments[2:], True)

def m4_substr(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_syscmd(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_sysval(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_traceoff(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_traceon(processor, arguments) :
	raise Exception("Not implemeneted yet")

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

def m4_undivert(processor, arguments) :
	raise Exception("Not implemeneted yet")

def m4_placeholder(processor, arguments) :
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


def define_user_macro(macros_tab, name, text, mode = "insert"):
	macro = Macro()
	macro.name = name
	macro.type = Macro.TOKEN_DATA_TEXT
	macro.data = text
	if mode == "insert":
		macros_tab[macro.name] = [macro]
	elif mode == "pushdef":
		if macro.name not in macros_tab:
			macros_tab[macro.name] = []
		macros_tab[macro.name].insert(0, macro)
	else:
		raise Exception("Unknown mode '%s' for macro insertion" % mode)


# mode is INSERT or PUSHDEF
def define_builtin(macros_tab, name, func, groks_macro_args, blind_if_no_args, mode = "insert"):
	macro = Macro()
	macro.name = name
	macro.macro_args = groks_macro_args
	macro.blind_no_args = blind_if_no_args
	macro.type = Macro.TOKEN_DATA_FUNC
	macro.data = func
	if mode == "insert":
		macros_tab[macro.name] = [macro]
	elif mode == "pushdef":
		if macro.name not in macros_tab:
			macros_tab[macro.name] = []
		macros_tab[macro.name].insert(0, macro)
	else:
		raise Exception("Unknown mode '%s' for macro insertion" % mode)

def lookup_macro(macros_tab, name, mode = 'lookup'):
	if name not in macros_tab:
		return None
	if mode == 'lookup':
		return macros_tab[name][0]
	elif mode == 'delete':
		macros_tab[name].pop(0)
		if len(macros_tab[name]) == 0:
			del macros_tab[name]	
	elif mode == 'popdef':
		del macros_tab[name]
	return None


def builtin_init(no_gnu_extensions = False, prefix_all_builtins = False):
	macros_tab = {}
	# builtin
	for name, gnu_extension, groks_macro_args, blind_if_no_args, func in builtin_tab:
		if no_gnu_extensions and gnu_extension:
			continue
		if prefix_all_builtins:
			name = "m4_" + name
		define_builtin(macros_tab, name, func, groks_macro_args, blind_if_no_args)
	# defines
	for unix_name, gnu_name, func in predefined_tab:
		if no_gnu_extensions:
			if unix_name:
				define_user_macro(macros_tab, unix_name, func)
		else:
			if gnu_name:
				define_user_macro(macros_tab, gnu_name, func)

	return macros_tab


if __name__ == "__main__":
	macros_tab = builtin_init()
