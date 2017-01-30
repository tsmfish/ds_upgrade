import re

print_message_format = "> {0} < : {1}"


class COLORS:

    class STYLE:
        normal    = 0
        highlight = 1
        underline = 4
        blink     = 5
        negative  = 7

    class FOREGROUND:
        black   = 30
        red     = 31
        green   = 32
        yellow  = 33
        blue    = 34
        magenta = 35
        cyan    = 36
        white   = 37

    class BACKGROUND:
        black   = 40
        red     = 41
        green   = 42
        yellow  = 43
        blue    = 44
        magenta = 45
        cyan    = 46
        white   = 47

    end = "\x1b[0m"
    colored = '\x1b[{style};{foreground};{background}m'

    black   = colored.format(style=STYLE.normal, foreground=FOREGROUND.black  , background=BACKGROUND.white)
    red     = colored.format(style=STYLE.normal, foreground=FOREGROUND.red    , background=BACKGROUND.black)
    green   = colored.format(style=STYLE.normal, foreground=FOREGROUND.green  , background=BACKGROUND.black)
    yellow  = colored.format(style=STYLE.normal, foreground=FOREGROUND.yellow , background=BACKGROUND.black)
    blue    = colored.format(style=STYLE.normal, foreground=FOREGROUND.blue   , background=BACKGROUND.black)
    magenta = colored.format(style=STYLE.normal, foreground=FOREGROUND.magenta, background=BACKGROUND.black)
    cyan    = colored.format(style=STYLE.normal, foreground=FOREGROUND.cyan   , background=BACKGROUND.black)
    white   = colored.format(style=STYLE.normal, foreground=FOREGROUND.white  , background=BACKGROUND.black)

    colors = [white,
              cyan,
              green,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.blue, background=BACKGROUND.cyan),
              yellow,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.blue, background=BACKGROUND.green),
              magenta,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.cyan, background=BACKGROUND.blue),
              black,
              colored.format(style=STYLE.normal, foreground=FOREGROUND.blue, background=BACKGROUND.yellow),
              ]

    warning = yellow
    fatal = colored.format(style=STYLE.highlight, foreground=FOREGROUND.red, background=BACKGROUND.black)
    error = red
    ok = green
    info = cyan


def print_for_ds(host, message, print_lock=None, log_file_name=None, host_color=None, message_color=None):

    if host_color:
        colored_host = host_color + host + COLORS.end
    else:
        if message_color:
            colored_host = message_color + host + COLORS.end
        else:
            colored_host = host
    if message_color:
        colored_message = message_color + message + COLORS.end
    else:
        if host_color:
            colored_message = host_color + message + COLORS.end
        else:
            colored_message = message

    if print_lock: print_lock.acquire()
    print print_message_format.format(colored_host, colored_message)
    if print_lock: print_lock.release()
    if log_file_name:
        try:
            with open(log_file_name, 'a') as log_file:
                log_file.write("{0}\n".format(message))
                log_file.close()
        except IOError:
            pass

def is_contains(regexp, text):
    """

    :param regexp:
    :param text:
    :return: True if string contains regular expression
    """
    if re.search(regexp, text):
        return True
    else:
        return False


def extract(regexp, text):
    """

    :param regexp: regular expression
    :param text: source for extracting
    :return: first occur regular expression
    """
    try:
        return re.findall(regexp, text)[0]
    except IndexError:
        return ""
