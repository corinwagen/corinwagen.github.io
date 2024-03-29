// Builds static .html files from a template.

// RSS code modified from https://medium.com/@etiennerouzeaud/a-rss-feed-valid-in-go-edfc22e410c7

package main
import (
    "fmt"
    "io/ioutil"
    "strings"
    "path/filepath"
    "os"
    fm "github.com/ericaro/frontmatter"
    "time"
    "sort"
    "strconv"
    "encoding/xml"
)

// config
const source_dir            string  = "src/"
const template_path         string  = "static/template.html"
const target_dir            string  = "public/main/"

// blog config
const blog_template_path    string  = "static/blog-template.html"
const blog_target_dir       string  = "public/blog/"
const date_input            string  = "2006-01-02"
const date_output           string  = "January 2, 2006"
const posts_per_page         int     = 5

// rss feed config - needs to go in root dir to be discoverable
const feed_target_path         string  = "rss.xml"

var page_template   string
var blog_template   string

type Page struct {
	Title   string  `yaml:"title"`
	IsBlog  bool    `yaml:"blog"`
	Date    string  `yaml:"date"`
	Summary string  `yaml:"summary"`
	Content string  `fm:"content" yaml:"-"`
    ImagePath string `yaml:"image"`
    Path    string
    DateObj time.Time
}

type Cdata struct {
    Value string `xml:",cdata"`
}

type RSSItem struct {
    Title       string `xml:"title"`
    Link        string `xml:"link"`
    Description Cdata  `xml:"description"`
    PubDate     string `xml:"pubDate"`
}

type rss struct {
    Version     string `xml:"version,attr"`
    Description string `xml:"channel>description"`
    Link        string `xml:"channel>link"`
    Title       string `xml:"channel>title"`

    Item []RSSItem `xml:"channel>item"`
}

var blog_posts = make([]Page, 0)

// Load a file with path ``name`` as a string.
func load_file(name string) string {
    file, _ := ioutil.ReadFile(name)
    return string(file)
}

// Write string ``text`` to path ``name``.
func write_file(name string, text string) {
    content := []byte(text)
    ioutil.WriteFile(name, content, 0644)
}

// Write RSS feed .xml file
func write_rss(pages []Page) {
    var rss_posts = make([]RSSItem, 0)
    for idx := 0; idx < len(blog_posts); idx++ {
        post := blog_posts[idx]

        // we want the full page text, so we need to put it all as XHTML CDATA
        var desc Cdata
        desc.Value = strings.Replace(post.Content, "../img", "https://corinwagen.github.io/public/img", -1)

        var rss_post = RSSItem{post.Title, post.Path, desc, post.DateObj.Format(time.RFC1123Z)}
        rss_posts = append(rss_posts, rss_post)
    }

    feed := &rss{
        Version:     "2.0",
        Description: "My personal blog, mainly focusing on issues of chemistry and metascience, unified by trying to answer the question \"how can we make science better\"?",
        Link:        "https://corinwagen.github.io",
        Title:       "Corin Wagen",
        Item:        rss_posts,
    }

    fo, err := os.Create(feed_target_path)
    if err != nil {
        panic(err)
    }

    // on exit, close fo
    defer func() {
        if err := fo.Close(); err != nil {
            panic(err)
        }
    }()

    enc := xml.NewEncoder(fo)
    enc.Indent("  ", "    ")
    if err := enc.Encode(feed); err != nil {
        fmt.Printf("error: %feed\n", err)
    }

    fmt.Println("Built RSS feed!")
}

// Build a given ``.html`` file with appropriate FrontMatter into a proper web page.
func build_page(path string, info os.FileInfo, err error) error {
    if info.IsDir() {
        return nil
    }

    text := load_file(path)
    post := new(Page)
    fm.Unmarshal(([]byte)(text), post)
    pieces := strings.Split(path, "/")
    post.Path = pieces[len(pieces)-1]

    var formatted_text string
    if post.IsBlog {
        formatted_text = strings.Replace(blog_template, "TITLE", post.Title, -1)
        formatted_text = strings.Replace(formatted_text, "CONTENT", post.Content, -1)
        formatted_text = strings.Replace(formatted_text, "SUMMARY", post.Summary, -1)

        if len(post.ImagePath) > 0 {
            formatted_text = strings.Replace(formatted_text, "IMAGE_PATH", post.ImagePath, -1)
        } else {
            formatted_text = strings.Replace(formatted_text, "<meta name=\"twitter:image\" content=\"IMAGE_PATH\" />", "", -1)
            formatted_text = strings.Replace(formatted_text, "summary_large_image", "summary", -1)
        }

        post.DateObj, _ = time.Parse(date_input, post.Date)
        formatted_text = strings.Replace(formatted_text, "DATE", post.DateObj.Format(date_output), -1)

        post.Path = blog_target_dir + post.Path
        blog_posts = append(blog_posts, *post)
    } else {
        formatted_text = strings.Replace(page_template, "TITLE", post.Title, -1)
        formatted_text = strings.Replace(formatted_text, "CONTENT", post.Content, -1)
        post.Path = target_dir + post.Path
    }

    fmt.Println("Building " + post.Path)
    write_file(post.Path, formatted_text)
    return nil
}

func main() {
    page_template = load_file(template_path)
    blog_template = load_file(blog_template_path)

    filepath.Walk(source_dir, build_page)

    // All we need to do now is build the blogroll and the archive.
    sort.Slice(blog_posts, func(i, j int) bool {
        return blog_posts[i].DateObj.After(blog_posts[j].DateObj)
    })

    // This is a bit messy, but gets the job done.
    current_page := "<h1 class='blogroll-header'>Blog</h1>"
    count := 0
    page_num := 1

    blog_archive := "<h1 class='blogroll-header'>Archive</h1>"

    if len(blog_posts) > posts_per_page {
        current_page = current_page + "<div class='next-link'><a href='blog_p" + strconv.Itoa(page_num + 1) + ".html'>next page</a></div>"
    }
    current_page = current_page + "<br>"

    for idx := 0; idx < len(blog_posts); idx++ {
        post := blog_posts[idx]

        current_page = current_page + "<div class='blogroll-container'><h2><a class='blogroll-title' href='../../" + post.Path  + "'>" + post.Title + "</a></h2><i>"
        current_page = current_page + post.DateObj.Format(date_output) + "</i>" + post.Content + "</div>"

        blog_archive = blog_archive + "<a href='../../" + post.Path  + "'>" + post.Title + "</a> (" + post.DateObj.Format(date_output) + ")<br>"

        count++
        if (count % posts_per_page == 0) || (idx + 1 == len(blog_posts)) {
            // finish old page
            if page_num > 1 {
                current_page = current_page + "<div class='previous-link'><a href='blog_p" + strconv.Itoa(page_num - 1) + ".html'>previous page</a></div>"
            }

            if idx + 1 < len(blog_posts) {
                current_page = current_page + "<div class='next-link'><a href='blog_p" + strconv.Itoa(page_num + 1) + ".html'>next page</a></div>"
            }
            current_page = current_page + "<br>"

            formatted_text := strings.Replace(page_template, "TITLE", "Blog", -1)
            formatted_text = strings.Replace(formatted_text, "CONTENT", current_page, -1)
            fmt.Println("Building " + target_dir + "blog_p" + strconv.Itoa(page_num) + ".html")
            write_file(target_dir + "blog_p" + strconv.Itoa(page_num) + ".html", formatted_text)

            // start new page
            current_page = "<h1 class='blogroll-header'>Blog</h1>"
            page_num++
            if page_num > 1 {
                current_page = current_page + "<div class='previous-link'><a href='blog_p" + strconv.Itoa(page_num - 1) + ".html'>previous page</a></div>"
            }

            if idx + posts_per_page + 1 < len(blog_posts) {
                current_page = current_page + "<div class='next-link'><a href='blog_p" + strconv.Itoa(page_num + 1) + ".html'>next page</a></div>"
            }
            current_page = current_page + "<br>"
        }
    }

    formatted_text := strings.Replace(page_template, "TITLE", "Archive", -1)
    formatted_text = strings.Replace(formatted_text, "CONTENT", blog_archive, -1)
    fmt.Println("Building " + target_dir + "archive.html")
    write_file(target_dir + "archive.html", formatted_text)

    write_rss(blog_posts)
}
