import os
import shutil
import paramiko
from dotenv import load_dotenv
import markdown2
from ebooklib import epub
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()

SFTP_HOST = os.getenv('SFTP_HOST')
SFTP_PORT = int(os.getenv('SFTP_PORT'))
SFTP_USER = os.getenv('SFTP_USER')
SFTP_PASSWORD = os.getenv('SFTP_PASSWORD')

local_folder = os.path.join(os.path.dirname(__file__), 'data')
temp_folder = os.path.join(os.path.dirname(__file__), 'temp')
remote_folder = '/mnt/onboard/sync'

def convert_md_to_epub(md_file, epub_file):
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    html_content = markdown2.markdown(md_content, extras=["break-on-newline"])
    soup = BeautifulSoup(html_content, 'html.parser')
    
    book = epub.EpubBook()
    book.set_identifier('id123456')
    book.set_title(os.path.splitext(os.path.basename(md_file))[0])
    book.set_language('en')
    
    chapters = []
    current_chapter = None
    chapter_count = 1
    
    for element in soup:
        if element.name and element.name.startswith('h'):
            if current_chapter:
                current_chapter.content = current_chapter.content.strip()
                chapters.append(current_chapter)
            current_chapter = epub.EpubHtml(title=element.text, file_name=f'chap_{chapter_count:02}.xhtml', lang='en')
            current_chapter.content = f'<h1>{element.text}</h1>'
            chapter_count += 1
        elif current_chapter:
            current_chapter.content += str(element)
    
    if current_chapter:
        current_chapter.content = current_chapter.content.strip()
        chapters.append(current_chapter)
    
    # If no chapters were created, treat the whole file as one chapter
    if not chapters:
        single_chapter = epub.EpubHtml(title=os.path.splitext(os.path.basename(md_file))[0], file_name='chap_01.xhtml', lang='en')
        single_chapter.content = html_content.strip()
        chapters.append(single_chapter)
    
    for chapter in chapters:
        book.add_item(chapter)
    
    style = 'BODY {color: white;}'
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)
    
    book.spine = ['nav'] + chapters
    
    epub.write_epub(epub_file, book, {})

def prepare_temp_folder(local_folder, temp_folder):
    if os.path.exists(temp_folder):
        shutil.rmtree(temp_folder)
    shutil.copytree(local_folder, temp_folder)
    
    for root, dirs, files in os.walk(temp_folder):
        for file in files:
            if file.endswith('.md'):
                md_file = os.path.join(root, file)
                epub_file = os.path.splitext(md_file)[0] + '.epub'
                convert_md_to_epub(md_file, epub_file)
                os.remove(md_file)

def sync_folder(sftp, local_folder, remote_folder):
    for root, dirs, files in os.walk(local_folder):
        remote_path = os.path.join(remote_folder, os.path.relpath(root, local_folder)).replace('\\', '/')
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            sftp.mkdir(remote_path)
        
        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(remote_path, file).replace('\\', '/')
            sftp.put(local_file, remote_file)

def main():
    prepare_temp_folder(local_folder, temp_folder)
    
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    transport.connect(username=SFTP_USER, password=SFTP_PASSWORD)
    
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    try:
        sync_folder(sftp, temp_folder, remote_folder)
    finally:
        sftp.close()
        transport.close()
        shutil.rmtree(temp_folder)

if __name__ == '__main__':
    main()