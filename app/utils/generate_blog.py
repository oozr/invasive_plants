import os
import markdown
import frontmatter
from datetime import datetime
from app.config import Config

class BlogGenerator:
    def __init__(self):
        self.blog_posts = self.generate_blog_posts()
        self.tags = self.generate_tags()

    @staticmethod
    def read_markdown_file(file_path):
        """Read and parse markdown file with frontmatter"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return frontmatter.loads(content)

    def generate_tags(self):
        """Generate a dictionary of all tags and their counts"""
        tags = {}
        for post in self.blog_posts:
            for tag in post.get('tags', []):
                tags[tag] = tags.get(tag, 0) + 1
        return tags

    def get_posts_by_tag(self, tag):
        """Filter posts by tag"""
        return [post for post in self.blog_posts if tag in post.get('tags', [])]

    def generate_blog_posts(self):
        """Generate list of blog posts from markdown files"""
        markdown_files = sorted([f for f in os.listdir(Config.BLOG_DIR) if f.endswith('.md')])
        blog_posts = []

        for filename in markdown_files:
            file_path = os.path.join(Config.BLOG_DIR, filename)
            post = self.read_markdown_file(file_path)
            
            metadata = post.metadata
            content = post.content

            # Generate excerpt if not provided
            excerpt = metadata.get('excerpt')
            if not excerpt:
                content_without_headers = "\n".join(
                    line for line in content.splitlines() 
                    if not line.strip().startswith('#')
                )
                excerpt = " ".join(content_without_headers.split()[:50]) + "..."

            # Convert Markdown to HTML
            html_content = markdown.markdown(
                content,
                extensions=['extra', 'toc', 'meta']
            )

            # Create URL-friendly slug from title
            slug = metadata.get('title', 'Untitled').lower()
            slug = ''.join(c if c.isalnum() or c.isspace() else '' for c in slug)
            slug = '-'.join(slug.split())

            blog_posts.append({
                "title": metadata.get('title', 'Untitled'),
                "date": metadata.get('date', datetime.now().strftime('%Y-%m-%d')),
                "author": metadata.get('author', Config.SITE_AUTHOR),
                "tags": metadata.get('tags', []),
                "excerpt": excerpt,
                "content": html_content,
                "slug": slug
            })

        return sorted(blog_posts, key=lambda x: x['date'], reverse=True)
        
    def get_post_by_slug(self, slug):
        """Get blog post by slug"""
        for post in self.blog_posts:
            if post["slug"] == slug:
                return post
        return None