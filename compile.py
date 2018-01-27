"""This file compiles all the provided post templates"""

from os import devnull, mkdir, path
from re import finditer, MULTILINE, sub
from shutil import rmtree
from subprocess import CalledProcessError, check_output

from glob import glob
from jinja2 import Environment, FileSystemLoader
from num2words import num2words

from wotw_highlighter import Block

POSTS_DIR = path.dirname(__file__)
ROOT_DIR = path.dirname(POSTS_DIR)
BUILD_DIR = path.join(POSTS_DIR, 'build')
TEMPLATE_DIR = path.join(POSTS_DIR, 'templates')

rmtree(BUILD_DIR, ignore_errors=True)
mkdir(BUILD_DIR)


def highlight_block(content, **kwargs):
    """Highlights a block via wotw-highlighter"""
    blob = Block(content, inline_css=True, **kwargs)
    return blob.highlighted_blob


def run_bash(command_as_tuple):
    """Runs the given command via check_output and returns its results"""
    output = ('$ %s\n' % (' '.join(command_as_tuple))).encode('utf-8')
    return ('%s%s' % (output, check_output(command_as_tuple))).decode('utf-8')


def include_with_default(current_tag, relative_path, language):
    """Includes the specified file from the given reference. Defaults to local
    version when not found."""
    language = language or path.splitext(path.basename(relative_path))[
        1].replace('.', '')
    new_include = "```%(language)s\n" % locals()
    new_include = new_include.replace('```yml', '```yaml')
    try:
        loaded_contents = check_output(
            ['git', 'show', current_tag + ':' + relative_path],
            stderr=open(devnull, 'w')
        )
    except CalledProcessError:
        with file(path.join(ROOT_DIR, relative_path), 'r') as file_to_include:
            loaded_contents = file_to_include.read()
    new_include += "%s\n" % (loaded_contents)
    new_include += '```\n'
    return new_include.decode('utf-8')


def link_header(matched_line, used_headlines):
    """Creates a Markdown TOC link"""
    headline = matched_line.group(2)
    cleaned_headline = sub('[^a-z]', '', headline.lower())
    if cleaned_headline in used_headlines:
        used_headlines[cleaned_headline] += 1
        cleaned_headline += str(used_headlines[cleaned_headline])
    else:
        used_headlines[cleaned_headline] = 0
    return "%s[%s](#%s)%s" % (
        matched_line.group(1),
        headline,
        cleaned_headline,
        matched_line.group(3)
    )


def render_single_post(post_basename, jinja_to_use):
    """Renders a specific post file with the provided environment"""
    template = jinja_to_use.get_template(post_basename)
    pre_toc = template.render(
        post_number=int(post_basename.split('-')[1]),
        current_tag=path.splitext(post_basename)[0].replace('.md', '')
    )
    return pre_toc.strip().encode('utf-8')


def build_post_toc(post_content):
    """Builds a Ghost-compatible TOC"""
    no_code_blocks = sub(r'```[\s\S]*?```', '', post_content)
    generated_toc = ""
    used_headlines = dict()
    for matched_header_line in finditer(r'^##(#*)\s*(.*)$', no_code_blocks, MULTILINE):
        headline = matched_header_line.group(2)
        cleaned_headline = sub('[^a-z]', '', headline.lower())
        if cleaned_headline in used_headlines:
            used_headlines[cleaned_headline] += 1
            cleaned_headline += str(used_headlines[cleaned_headline])
        else:
            used_headlines[cleaned_headline] = 0
        generated_toc += "%s- [%s](#%s)\n" % (
            sub('#', '  ', matched_header_line.group(1)),
            headline,
            cleaned_headline
        )
    finalized_toc = sub(
        r'[^\n]*<!--\s*?wotw_toc\s*?-->[^\n]*',
        generated_toc,
        post_content
    )
    return finalized_toc


def strip_extra_whitespace(contents):
    """Removes uncessary whitespace"""
    contents = sub(r'\n\n+', '\n\n', contents)
    contents = sub(r'\n\n```\n\n', '\n```\n\n', contents)
    return contents


def fully_compile_single_post(post_path, jinja_to_use):
    """Run all the steps to compile a single post"""
    post_basename = path.basename(post_path)
    initial_pass = render_single_post(post_basename, jinja_to_use)
    toc_pass = build_post_toc(initial_pass)
    final_pass = strip_extra_whitespace(toc_pass)
    output_filename = path.join(BUILD_DIR, post_basename.replace('.j2', ''))
    with file(output_filename, 'w+') as built_file:
        built_file.write(final_pass)


def compile_all_posts():
    """Create the Jinja environment, load the posts, and build everything"""
    jinja_env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR)
    )

    jinja_env.globals['highlight_block'] = highlight_block
    jinja_env.globals['include_with_default'] = include_with_default
    jinja_env.globals['num2words'] = num2words
    jinja_env.globals['run_bash'] = run_bash

    for post_filename in glob(path.join(TEMPLATE_DIR, 'post-*.j2')):
        fully_compile_single_post(post_filename, jinja_env)

compile_all_posts()
