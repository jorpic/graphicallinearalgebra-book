import os
import subprocess
import cgi
import pypandoc
import requests
from bs4 import BeautifulSoup
from PIL import Image

BUILD_DIR = 'build'
URL = 'https://graphicallinearalgebra.net'

def get_soup(url, selector):
    req = requests.get(url)
    assert req.status_code == 200, req.content
    soup = BeautifulSoup(req.content, features='lxml')
    return soup.select(selector)

def save_img(url, path, name):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        mimetype, _ = cgi.parse_header(r.headers['content-type'])
        _, img_type = mimetype.split('/')
        img_path = os.path.join(path, name + '.' + img_type)
        with open(img_path, 'wb') as f:
            for chunk in r.iter_content(1024):
                f.write(chunk)

        # mupdf is not happy with GIFs, so we convert them into PNGs here
        if img_path.endswith('.gif'):
            img = Image.open(img_path)
            png_path = img_path + '.png'
            img.save(png_path, 'png', optimize=True, quality=90)
            os.remove(img_path)
            img_path = png_path

        return img_path


def get_article_md(url):
    ascii_name = url.strip('/').split('/')[-1]

    article_path = os.path.join(BUILD_DIR, ascii_name)
    os.mkdir(article_path)

    root = get_soup(url, 'article')[0]
    title = root.select_one('.entry-title')
    content = root.select_one('.entry-content')

    title.attrs = {}
    content.attrs = {}
    content.select_one('#jp-post-flair').decompose()
    # unwrap local links
    for a in content.select('a[href^="#"]'):
        a.unwrap()
    # unwrap links to images
    for a in content.select('a img'):
        a.parent.unwrap()
    # drop empty image refs
    for a in content.select('a[href$=".gif"]'):
        a.decompose()
    for s in content.select('span[style]'):
        s.unwrap()

    img_count = 1
    for i in content.select('img'):
        img_path = save_img(i.attrs['src'], article_path, str(img_count))
        i.attrs = {'src': './' + img_path, 'alt': '.'}
        img_count += 1

    article = BeautifulSoup()
    article.append(title)
    article.append(content)
    md = pypandoc.convert_text(article, 'md', format='html')
    md_path = os.path.join(article_path, 'text.md')
    with open(md_path, 'w') as f:
        f.write(md)

    return md_path


os.mkdir(BUILD_DIR)

def is_episode_title(text):
    return text.startswith('Episode') \
        or text == 'Why string diagrams?' \
        or text == 'Orthogonality and projections' \
        or text == 'Eigenstuff, diagrammatically'\
        or text.startswith('Determinants')

articles = []
for a in get_soup(URL, '.entry-content a'):
    if is_episode_title(a.text):
        article_url = a.attrs['href']
        print(article_url)
        article_path = get_article_md(article_url)
        articles.append(article_path)

# was not able to  run pypandoc.convert_file
# pypandoc.convert_file(
#     'book.yaml',
#      outputfile='build/book.epub',
#      extra_args=articles)
args = ['pandoc', '-o', 'build/book.epub', '--toc', 'book.yaml'] + articles
subprocess.run(args)

# use calibre to convert epub to mobi
subprocess.run(['ebook-convert', 'build/book.epub', 'build/book.mobi'])
