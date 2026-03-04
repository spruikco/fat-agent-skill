# WordPress -- Framework Fix Reference

Theme and plugin development patterns for fixing common post-launch issues found
by FAT Agent. This file covers **theme-level code** (`functions.php`, templates,
hooks). For server/hosting configuration (`.htaccess`, `wp-config.php`, PHP
settings), see the platform-fixes reference instead.

All code examples go in the active theme's `functions.php` (or a custom plugin)
unless otherwise noted. When working with a parent theme, **always use a child
theme** so updates don't erase your changes.

---

## SEO Meta Tags

### The wp_head Hook

Every WordPress theme calls `wp_head()` just before `</head>`. This is the
primary insertion point for meta tags, structured data, and tracking scripts.

```php
// functions.php -- add a meta description to every page
add_action('wp_head', 'fat_add_meta_description');
function fat_add_meta_description() {
    if (is_front_page()) {
        echo '<meta name="description" content="' . esc_attr(get_bloginfo('description')) . '">' . "\n";
    } elseif (is_singular()) {
        $post = get_queried_object();
        $excerpt = wp_strip_all_tags($post->post_excerpt);
        if ($excerpt) {
            echo '<meta name="description" content="' . esc_attr(wp_trim_words($excerpt, 25)) . '">' . "\n";
        }
    }
}
```

### Plugin Approach (Yoast SEO / Rank Math)

For most sites, a dedicated SEO plugin is the right answer. Yoast SEO and
Rank Math both handle title tags, meta descriptions, Open Graph tags, Twitter
Cards, canonical URLs, and XML sitemaps automatically.

**FAT Agent recommendation:** If the site has no SEO plugin and is missing
multiple meta tags, recommend installing one rather than hand-rolling everything.
If only one or two tags are missing and the client prefers minimal plugins,
use the manual approach below.

Check whether an SEO plugin is active before adding manual meta:

```php
// Avoid conflicts -- only add manual meta if no SEO plugin is present
function fat_has_seo_plugin() {
    return defined('WPSEO_VERSION')          // Yoast SEO
        || defined('RANK_MATH_VERSION')      // Rank Math
        || defined('AIOSEO_VERSION');        // All in One SEO
}

add_action('wp_head', 'fat_add_meta_description');
function fat_add_meta_description() {
    if (fat_has_seo_plugin()) {
        return; // Let the plugin handle it
    }
    // ... manual meta tag output
}
```

### Title Tag Support

WordPress 4.1+ supports automatic `<title>` output. Many older themes still
hardcode `<title>` in `header.php`. The modern approach:

```php
// functions.php -- enable automatic <title> tag
add_theme_support('title-tag');
```

Then **remove** any hardcoded `<title>` from `header.php`. WordPress will
generate `Page Title - Site Name` by default.

### Customising the Title

Use the `document_title_parts` filter (WordPress 4.4+) to modify the
generated title:

```php
add_filter('document_title_parts', 'fat_custom_title_parts');
function fat_custom_title_parts($title_parts) {
    if (is_front_page()) {
        $title_parts['title'] = 'Your Custom Homepage Title';
    }

    // Change the separator (default is a dash)
    // This is handled by document_title_separator filter instead

    return $title_parts;
}

// Change the title separator from "-" to "|"
add_filter('document_title_separator', function () {
    return '|';
});
```

The older `wp_title` filter still works but `document_title_parts` is preferred.

### Complete functions.php SEO Setup (No Plugin)

A minimal but complete SEO setup for themes without an SEO plugin:

```php
// === SEO META TAGS (no-plugin approach) ===

add_theme_support('title-tag');

add_action('wp_head', 'fat_seo_meta_tags', 1);
function fat_seo_meta_tags() {
    if (fat_has_seo_plugin()) {
        return;
    }

    $title       = '';
    $description = '';
    $og_type     = 'website';
    $og_image    = '';

    if (is_front_page()) {
        $title       = get_bloginfo('name');
        $description = get_bloginfo('description');
    } elseif (is_singular()) {
        $post        = get_queried_object();
        $title       = get_the_title($post);
        $description = $post->post_excerpt
            ? wp_strip_all_tags($post->post_excerpt)
            : wp_trim_words(wp_strip_all_tags($post->post_content), 25);
        $og_type     = is_single() ? 'article' : 'website';

        if (has_post_thumbnail($post)) {
            $og_image = get_the_post_thumbnail_url($post, 'large');
        }
    } elseif (is_archive()) {
        $title       = get_the_archive_title();
        $description = get_the_archive_description();
    }

    $canonical = is_singular() ? get_permalink() : home_url(add_query_arg([]));

    if ($description) {
        $description = wp_trim_words($description, 25);
        echo '<meta name="description" content="' . esc_attr($description) . '">' . "\n";
    }

    echo '<link rel="canonical" href="' . esc_url($canonical) . '">' . "\n";

    // Open Graph
    echo '<meta property="og:title" content="' . esc_attr($title) . '">' . "\n";
    echo '<meta property="og:description" content="' . esc_attr($description) . '">' . "\n";
    echo '<meta property="og:type" content="' . esc_attr($og_type) . '">' . "\n";
    echo '<meta property="og:url" content="' . esc_url($canonical) . '">' . "\n";
    echo '<meta property="og:site_name" content="' . esc_attr(get_bloginfo('name')) . '">' . "\n";
    if ($og_image) {
        echo '<meta property="og:image" content="' . esc_url($og_image) . '">' . "\n";
    }

    // Twitter Card
    echo '<meta name="twitter:card" content="summary_large_image">' . "\n";
    echo '<meta name="twitter:title" content="' . esc_attr($title) . '">' . "\n";
    echo '<meta name="twitter:description" content="' . esc_attr($description) . '">' . "\n";
    if ($og_image) {
        echo '<meta name="twitter:image" content="' . esc_url($og_image) . '">' . "\n";
    }
}
```

---

## Structured Data (JSON-LD)

### Output via wp_head

JSON-LD should appear inside `<head>` (or anywhere in the document, but `<head>`
is conventional). Use `wp_head` with a late priority so it fires after other
meta output.

```php
add_action('wp_head', 'fat_jsonld_schema', 99);
function fat_jsonld_schema() {
    if (is_front_page()) {
        $schema = [
            '@context' => 'https://schema.org',
            '@type'    => 'WebSite',
            'name'     => get_bloginfo('name'),
            'url'      => home_url('/'),
        ];

        // Add search action for sitelinks search box
        $schema['potentialAction'] = [
            '@type'       => 'SearchAction',
            'target'      => home_url('/?s={search_term_string}'),
            'query-input' => 'required name=search_term_string',
        ];

        echo '<script type="application/ld+json">' . "\n";
        echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
        echo "\n" . '</script>' . "\n";
    }

    if (is_singular('post')) {
        $post  = get_queried_object();
        $image = has_post_thumbnail($post)
            ? get_the_post_thumbnail_url($post, 'large')
            : '';

        $schema = [
            '@context'      => 'https://schema.org',
            '@type'         => 'Article',
            'headline'      => get_the_title($post),
            'datePublished' => get_the_date('c', $post),
            'dateModified'  => get_the_modified_date('c', $post),
            'author'        => [
                '@type' => 'Person',
                'name'  => get_the_author_meta('display_name', $post->post_author),
            ],
            'publisher'     => [
                '@type' => 'Organization',
                'name'  => get_bloginfo('name'),
            ],
        ];

        if ($image) {
            $schema['image'] = $image;
        }

        echo '<script type="application/ld+json">' . "\n";
        echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
        echo "\n" . '</script>' . "\n";
    }
}
```

### Plugin-Generated Schema

Yoast SEO and Rank Math both generate comprehensive JSON-LD automatically. If
either plugin is active, avoid adding duplicate schema:

```php
add_action('wp_head', 'fat_jsonld_schema', 99);
function fat_jsonld_schema() {
    if (fat_has_seo_plugin()) {
        return;
    }
    // ... manual schema output
}
```

### wp_json_encode for Safe Output

Always use `wp_json_encode()` instead of `json_encode()`. It is a WordPress
wrapper that handles UTF-8 edge cases and is safe for output in `<script>` tags.
The `JSON_UNESCAPED_SLASHES` flag keeps URLs readable.

```php
// Good
echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES);

// Bad -- may produce incorrect encoding in some PHP/WordPress environments
echo json_encode($schema);
```

### LocalBusiness Schema (Common for Small Business Sites)

```php
add_action('wp_head', 'fat_local_business_schema', 99);
function fat_local_business_schema() {
    if (!is_front_page()) {
        return;
    }

    $schema = [
        '@context'    => 'https://schema.org',
        '@type'       => 'LocalBusiness',
        'name'        => get_bloginfo('name'),
        'url'         => home_url('/'),
        'telephone'   => '+1-555-123-4567',    // Replace with real data
        'address'     => [
            '@type'           => 'PostalAddress',
            'streetAddress'   => '123 Main St',
            'addressLocality' => 'Springfield',
            'addressRegion'   => 'IL',
            'postalCode'      => '62701',
            'addressCountry'  => 'US',
        ],
        'openingHoursSpecification' => [
            [
                '@type'     => 'OpeningHoursSpecification',
                'dayOfWeek' => ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
                'opens'     => '09:00',
                'closes'    => '17:00',
            ],
        ],
    ];

    echo '<script type="application/ld+json">' . "\n";
    echo wp_json_encode($schema, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT);
    echo "\n" . '</script>' . "\n";
}
```

---

## Image Optimization

### Featured Images / Post Thumbnails

Enable featured image support and define custom sizes:

```php
// functions.php
add_theme_support('post-thumbnails');

// Custom image sizes
add_image_size('hero-banner', 1920, 800, true);   // Hard crop
add_image_size('card-thumb', 600, 400, true);      // Hard crop
add_image_size('blog-wide', 1200, 0, false);       // Proportional height
```

### wp_get_attachment_image (Responsive srcset)

WordPress automatically generates `srcset` and `sizes` attributes when you
use its image functions. This is the correct way to output images:

```php
// In a template -- outputs <img> with srcset automatically
echo wp_get_attachment_image(
    get_post_thumbnail_id(),
    'large',
    false,
    ['class' => 'hero-image', 'loading' => 'lazy']
);
```

Output will look like:
```html
<img src="image-1024x768.jpg"
     srcset="image-300x225.jpg 300w, image-768x576.jpg 768w, image-1024x768.jpg 1024w"
     sizes="(max-width: 1024px) 100vw, 1024px"
     class="hero-image"
     loading="lazy"
     alt="The alt text from media library">
```

**Common mistake:** Using raw `<img src="<?php echo $url; ?>">` instead of
`wp_get_attachment_image()`. This loses srcset, alt text, and lazy loading.

### Custom Sizes in the Block Editor

Make custom sizes available in the block editor (Gutenberg):

```php
add_filter('image_size_names_choose', 'fat_custom_image_size_names');
function fat_custom_image_size_names($sizes) {
    return array_merge($sizes, [
        'hero-banner' => __('Hero Banner', 'theme-textdomain'),
        'card-thumb'  => __('Card Thumbnail', 'theme-textdomain'),
    ]);
}
```

### Lazy Loading

WordPress 5.5+ adds `loading="lazy"` to images and iframes by default.
To customise this behaviour:

```php
// Disable lazy loading on the first (hero) image to improve LCP
add_filter('wp_img_tag_add_loading_attr', 'fat_skip_lazy_hero', 10, 3);
function fat_skip_lazy_hero($value, $image, $context) {
    // Skip lazy load for images with the 'hero-image' class
    if (strpos($image, 'hero-image') !== false) {
        return false; // No loading attribute -- browser loads immediately
    }
    return $value;
}

// Or disable lazy loading globally (rarely recommended)
add_filter('wp_lazy_loading_enabled', '__return_false');
```

### WebP Conversion

**Plugin approach (recommended):** ShortPixel, Imagify, or EWWW Image Optimizer
will convert uploads to WebP automatically and serve them with `<picture>`
elements or rewrite rules.

**Theme-level approach** -- if the server supports it and you want to avoid a
plugin, add WebP upload support:

```php
// Allow WebP uploads in the media library
add_filter('mime_types', 'fat_allow_webp_uploads');
function fat_allow_webp_uploads($mimes) {
    $mimes['webp'] = 'image/webp';
    return $mimes;
}

// Fix WebP thumbnail display in media library (WordPress < 6.0)
add_filter('file_is_displayable_image', 'fat_webp_displayable', 10, 2);
function fat_webp_displayable($result, $path) {
    if (str_ends_with($path, '.webp')) {
        return true;
    }
    return $result;
}
```

### CDN Integration

Most CDN setups are handled at the server/plugin level, but the theme can
help by ensuring all asset URLs go through WordPress functions (which CDN
plugins can then rewrite):

```php
// Good -- CDN plugins can filter these URLs
get_template_directory_uri() . '/assets/img/logo.svg'
wp_get_attachment_url($attachment_id)
wp_get_attachment_image_src($attachment_id, 'large')

// Bad -- hardcoded URLs that CDN plugins cannot rewrite
'/wp-content/themes/mytheme/assets/img/logo.svg'
'https://example.com/wp-content/uploads/2024/01/photo.jpg'
```

For manual CDN rewriting without a plugin:

```php
// Replace the default upload URL with a CDN URL
add_filter('wp_get_attachment_url', 'fat_cdn_attachment_url');
function fat_cdn_attachment_url($url) {
    $upload_dir = wp_get_upload_dir();
    $cdn_base   = 'https://cdn.example.com/wp-content/uploads';
    return str_replace($upload_dir['baseurl'], $cdn_base, $url);
}
```

---

## Accessibility Patterns

### HTML5 Theme Support

Declare HTML5 support so WordPress outputs modern markup instead of XHTML
relics:

```php
add_theme_support('html5', [
    'search-form',
    'comment-form',
    'comment-list',
    'gallery',
    'caption',
    'style',
    'script',
]);
```

Without this, WordPress outputs `type="text/javascript"` on script tags
and other legacy attributes.

### Accessible Navigation (Custom Walker)

The default WordPress menu output is functional but lacks ARIA attributes
for dropdown submenus. A custom walker adds them:

```php
class Fat_Accessible_Nav_Walker extends Walker_Nav_Menu {

    /**
     * Add aria-haspopup and aria-expanded to items with children.
     */
    public function start_el(&$output, $item, $depth = 0, $args = null, $id = 0) {
        $classes   = empty($item->classes) ? [] : (array) $item->classes;
        $classes[] = 'menu-item-' . $item->ID;

        $class_string = implode(' ', apply_filters('nav_menu_css_class', array_filter($classes), $item, $args, $depth));
        $class_string = $class_string ? ' class="' . esc_attr($class_string) . '"' : '';

        $output .= '<li' . $class_string . '>';

        $atts = [
            'title'  => !empty($item->attr_title) ? $item->attr_title : '',
            'target' => !empty($item->target) ? $item->target : '',
            'rel'    => !empty($item->xfn) ? $item->xfn : '',
            'href'   => !empty($item->url) ? $item->url : '',
        ];

        // Add ARIA attributes for items with submenus
        if (in_array('menu-item-has-children', $classes, true)) {
            $atts['aria-haspopup'] = 'true';
            $atts['aria-expanded'] = 'false';
        }

        $attributes = '';
        foreach ($atts as $attr => $value) {
            if (!empty($value)) {
                $attributes .= ' ' . $attr . '="' . esc_attr($value) . '"';
            }
        }

        $title = apply_filters('the_title', $item->title, $item->ID);

        $output .= '<a' . $attributes . '>' . $title . '</a>';
    }
}

// Register the walker in your menu call (header.php or wherever menus render)
// wp_nav_menu([
//     'theme_location' => 'primary',
//     'container'      => 'nav',
//     'container_class' => 'main-navigation',
//     'container_id'   => 'site-navigation',
//     'walker'         => new Fat_Accessible_Nav_Walker(),
//     'items_wrap'     => '<ul id="%1$s" class="%2$s" role="menubar">%3$s</ul>',
// ]);
```

### Skip Link

Add a skip link as the very first element inside `<body>` in `header.php`:

```html
<!-- header.php, immediately after <body> -->
<a class="skip-link screen-reader-text" href="#primary">
    <?php esc_html_e('Skip to content', 'theme-textdomain'); ?>
</a>
```

The CSS (in `style.css` or your stylesheet):

```css
.skip-link {
    position: absolute;
    top: -100%;
    left: 0;
    z-index: 999;
    padding: 0.5rem 1rem;
    background: #000;
    color: #fff;
    text-decoration: none;
    font-weight: 700;
}

.skip-link:focus {
    top: 0;
}
```

### Screen Reader Text Class

WordPress core themes use `.screen-reader-text`. Provide it in your theme:

```css
/* Visually hide text but keep it accessible to screen readers */
.screen-reader-text {
    border: 0;
    clip: rect(1px, 1px, 1px, 1px);
    clip-path: inset(50%);
    height: 1px;
    margin: -1px;
    overflow: hidden;
    padding: 0;
    position: absolute;
    width: 1px;
    word-wrap: normal !important;
}

.screen-reader-text:focus {
    background-color: #f1f1f1;
    border-radius: 3px;
    box-shadow: 0 0 2px 2px rgba(0, 0, 0, 0.6);
    clip: auto !important;
    clip-path: none;
    color: #21759b;
    display: block;
    font-size: 0.875rem;
    font-weight: 700;
    height: auto;
    left: 5px;
    line-height: normal;
    padding: 15px 23px 14px;
    text-decoration: none;
    top: 5px;
    width: auto;
    z-index: 100000;
}
```

### ARIA Landmarks in Theme Templates

Proper landmark usage in theme template files:

```php
<!-- header.php -->
<header id="masthead" class="site-header" role="banner">
    <nav id="site-navigation" class="main-navigation" role="navigation"
         aria-label="<?php esc_attr_e('Primary Menu', 'theme-textdomain'); ?>">
        <?php wp_nav_menu(['theme_location' => 'primary']); ?>
    </nav>
</header>

<!-- index.php / page.php / single.php -->
<main id="primary" class="site-main" role="main">
    <!-- Page content here -->
</main>

<aside id="secondary" class="widget-area" role="complementary"
       aria-label="<?php esc_attr_e('Sidebar', 'theme-textdomain'); ?>">
    <?php dynamic_sidebar('sidebar-1'); ?>
</aside>

<!-- footer.php -->
<footer id="colophon" class="site-footer" role="contentinfo">
    <nav class="footer-navigation" role="navigation"
         aria-label="<?php esc_attr_e('Footer Menu', 'theme-textdomain'); ?>">
        <?php wp_nav_menu(['theme_location' => 'footer']); ?>
    </nav>
</footer>
```

**Note:** When you use semantic HTML5 elements (`<header>`, `<nav>`, `<main>`,
`<aside>`, `<footer>`), the `role` attributes are technically redundant in
modern browsers. They are included here for backward compatibility with older
assistive technology. The `aria-label` attributes are the important part --
they differentiate multiple landmarks of the same type (e.g., primary nav vs
footer nav).

### Accessible Forms

```php
<!-- searchform.php -->
<form role="search" method="get" class="search-form"
      action="<?php echo esc_url(home_url('/')); ?>">
    <label for="search-field" class="screen-reader-text">
        <?php esc_html_e('Search for:', 'theme-textdomain'); ?>
    </label>
    <input type="search"
           id="search-field"
           class="search-field"
           placeholder="<?php esc_attr_e('Search...', 'theme-textdomain'); ?>"
           value="<?php echo get_search_query(); ?>"
           name="s"
           required>
    <button type="submit" class="search-submit">
        <span class="screen-reader-text">
            <?php esc_html_e('Search', 'theme-textdomain'); ?>
        </span>
        <!-- Icon here -->
    </button>
</form>
```

For contact forms (Contact Form 7, WPForms, Gravity Forms), verify that the
plugin output includes proper `<label>` elements. If not, use the plugin's
settings to add them -- do not try to fix it in theme code.

---

## Performance Optimization

### Script Enqueuing with defer/async (WordPress 6.3+)

WordPress 6.3 introduced the `strategy` parameter for `wp_enqueue_script`:

```php
add_action('wp_enqueue_scripts', 'fat_enqueue_assets');
function fat_enqueue_assets() {
    // Defer non-critical JS (loads after HTML parsing)
    wp_enqueue_script(
        'theme-main',
        get_template_directory_uri() . '/assets/js/main.js',
        [],                   // dependencies
        wp_get_theme()->get('Version'),
        [
            'in_footer' => true,
            'strategy'  => 'defer',
        ]
    );

    // Async for independent scripts (loads in parallel, executes immediately)
    wp_enqueue_script(
        'theme-analytics-helper',
        get_template_directory_uri() . '/assets/js/analytics-helper.js',
        [],
        wp_get_theme()->get('Version'),
        [
            'in_footer' => true,
            'strategy'  => 'async',
        ]
    );

    // Enqueue stylesheets
    wp_enqueue_style(
        'theme-style',
        get_stylesheet_uri(),
        [],
        wp_get_theme()->get('Version')
    );
}
```

**For WordPress < 6.3**, add defer/async manually via a filter:

```php
add_filter('script_loader_tag', 'fat_add_defer_attribute', 10, 3);
function fat_add_defer_attribute($tag, $handle, $src) {
    $defer_scripts = ['theme-main', 'theme-analytics-helper'];
    if (in_array($handle, $defer_scripts, true)) {
        return str_replace(' src=', ' defer src=', $tag);
    }
    return $tag;
}
```

### Dequeuing Unused Plugin CSS

Plugins often load their CSS on every page. Remove it where it is not needed:

```php
add_action('wp_enqueue_scripts', 'fat_dequeue_unused_styles', 100);
function fat_dequeue_unused_styles() {
    // Remove Contact Form 7 CSS from pages without a form
    if (!is_page('contact')) {
        wp_dequeue_style('contact-form-7');
        wp_dequeue_script('contact-form-7');
    }

    // Remove WooCommerce styles from non-shop pages
    if (function_exists('is_woocommerce') && !is_woocommerce() && !is_cart() && !is_checkout() && !is_account_page()) {
        wp_dequeue_style('woocommerce-general');
        wp_dequeue_style('woocommerce-layout');
        wp_dequeue_style('woocommerce-smallscreen');
        wp_dequeue_script('wc-cart-fragments');
    }

    // Remove block library CSS if not using Gutenberg on the frontend
    // (only do this if you are certain no block content is rendered)
    // wp_dequeue_style('wp-block-library');
}
```

### Preconnect and Preload via wp_resource_hints

```php
// Preconnect to external domains (fonts, CDNs, analytics)
add_filter('wp_resource_hints', 'fat_resource_hints', 10, 2);
function fat_resource_hints($urls, $relation_type) {
    if ($relation_type === 'preconnect') {
        $urls[] = [
            'href'        => 'https://fonts.googleapis.com',
            'crossorigin' => 'anonymous',
        ];
        $urls[] = [
            'href'        => 'https://fonts.gstatic.com',
            'crossorigin' => 'anonymous',
        ];
    }
    return $urls;
}

// Preload critical assets (e.g., hero image, above-fold font)
add_action('wp_head', 'fat_preload_assets', 1);
function fat_preload_assets() {
    // Preload the primary font file
    echo '<link rel="preload" href="' . esc_url(get_template_directory_uri() . '/assets/fonts/main.woff2') . '" as="font" type="font/woff2" crossorigin="anonymous">' . "\n";
}
```

### Object Caching

Object caching is primarily a server-level concern (Redis, Memcached), but
themes should be written to benefit from it. WordPress caches database queries
automatically when an object cache backend is available. Theme code does not
need to change, but avoid patterns that bypass the cache:

```php
// Good -- uses WP_Query which respects the object cache
$recent_posts = new WP_Query([
    'posts_per_page' => 5,
    'post_status'    => 'publish',
]);

// Bad -- direct database query bypasses the object cache
global $wpdb;
$recent_posts = $wpdb->get_results("SELECT * FROM {$wpdb->posts} LIMIT 5");
```

### Transients API for Expensive Queries

Cache the result of expensive operations using the Transients API. When an
object cache is available, transients are stored there instead of the database.

```php
function fat_get_popular_posts() {
    $popular = get_transient('fat_popular_posts');
    if ($popular !== false) {
        return $popular;
    }

    // Expensive query
    $popular = new WP_Query([
        'posts_per_page' => 10,
        'meta_key'       => 'post_views_count',
        'orderby'        => 'meta_value_num',
        'order'          => 'DESC',
        'post_status'    => 'publish',
        'no_found_rows'  => true,          // Skip counting total rows (faster)
        'fields'         => 'ids',          // Only fetch post IDs (faster)
    ]);

    // Cache for 1 hour
    set_transient('fat_popular_posts', $popular->posts, HOUR_IN_SECONDS);

    return $popular->posts;
}

// Invalidate when a post is saved
add_action('save_post', function () {
    delete_transient('fat_popular_posts');
});
```

### Remove Unused Default Features

WordPress loads several features by default that many sites do not need:

```php
add_action('init', 'fat_remove_unused_features');
function fat_remove_unused_features() {
    // Remove emoji scripts and styles
    remove_action('wp_head', 'print_emoji_detection_script', 7);
    remove_action('wp_print_styles', 'print_emoji_styles');
    remove_action('admin_print_scripts', 'print_emoji_detection_script');
    remove_action('admin_print_styles', 'print_emoji_styles');
    remove_filter('the_content_feed', 'wp_staticize_emoji');
    remove_filter('comment_text_rss', 'wp_staticize_emoji');
    remove_filter('wp_mail', 'wp_staticize_emoji_for_email');

    // Remove oEmbed discovery (if you don't use embeds)
    remove_action('wp_head', 'wp_oembed_add_discovery_links');

    // Remove RSD link (for blog editing clients -- rarely used)
    remove_action('wp_head', 'rsd_link');

    // Remove Windows Live Writer manifest (legacy)
    remove_action('wp_head', 'wlwmanifest_link');

    // Remove WordPress version number (minor security benefit)
    remove_action('wp_head', 'wp_generator');

    // Remove shortlink
    remove_action('wp_head', 'wp_shortlink_wp_head');
}

// Disable the emoji DNS prefetch
add_filter('emoji_svg_url', '__return_false');

// Remove jQuery Migrate (if your theme/plugins don't need it)
add_action('wp_default_scripts', function ($scripts) {
    if (!is_admin() && isset($scripts->registered['jquery'])) {
        $scripts->registered['jquery']->deps = array_diff(
            $scripts->registered['jquery']->deps,
            ['jquery-migrate']
        );
    }
});
```

### Disable Global Styles for Classic Themes

WordPress 5.9+ injects global styles even on classic themes. If you do not
need them:

```php
add_action('wp_enqueue_scripts', 'fat_remove_global_styles', 100);
function fat_remove_global_styles() {
    wp_dequeue_style('global-styles');
    wp_dequeue_style('classic-theme-styles');
}
```

---

## Analytics Integration

### wp_head / wp_footer Hooks

The standard way to add third-party tracking scripts:

```php
// Google Analytics 4 (gtag.js) via wp_head
add_action('wp_head', 'fat_google_analytics', 1);
function fat_google_analytics() {
    if (is_user_logged_in() || wp_get_environment_type() !== 'production') {
        return; // Don't track logged-in users or non-production environments
    }
    $ga_id = 'G-XXXXXXXXXX'; // Replace with actual measurement ID
    ?>
    <script async src="https://www.googletagmanager.com/gtag/js?id=<?php echo esc_attr($ga_id); ?>"></script>
    <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', '<?php echo esc_js($ga_id); ?>');
    </script>
    <?php
}

// Google Tag Manager (container snippet) -- head portion
add_action('wp_head', 'fat_gtm_head', 1);
function fat_gtm_head() {
    if (is_user_logged_in() || wp_get_environment_type() !== 'production') {
        return;
    }
    $gtm_id = 'GTM-XXXXXXX';
    ?>
    <script>
    (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','<?php echo esc_js($gtm_id); ?>');
    </script>
    <?php
}

// Google Tag Manager -- noscript fallback (immediately after <body> in header.php)
// This needs to be placed directly in header.php, not in a hook, because
// wp_body_open fires after <body> but support varies by theme.
add_action('wp_body_open', 'fat_gtm_body');
function fat_gtm_body() {
    if (is_user_logged_in() || wp_get_environment_type() !== 'production') {
        return;
    }
    $gtm_id = 'GTM-XXXXXXX';
    ?>
    <noscript><iframe src="https://www.googletagmanager.com/ns.html?id=<?php echo esc_attr($gtm_id); ?>"
    height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
    <?php
}
```

### Enqueuing Analytics Properly

If you want WordPress to manage the analytics script (so caching/optimization
plugins can process it):

```php
add_action('wp_enqueue_scripts', 'fat_enqueue_analytics');
function fat_enqueue_analytics() {
    if (is_user_logged_in() || wp_get_environment_type() !== 'production') {
        return;
    }

    $ga_id = 'G-XXXXXXXXXX';

    wp_enqueue_script(
        'google-gtag',
        'https://www.googletagmanager.com/gtag/js?id=' . $ga_id,
        [],
        null,
        ['strategy' => 'async', 'in_footer' => false]
    );

    wp_add_inline_script('google-gtag', sprintf(
        "window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', %s);",
        wp_json_encode($ga_id)
    ));
}
```

### Site Kit by Google (Plugin Approach)

For non-technical clients, Site Kit by Google is the recommended plugin. It
connects Google Analytics, Search Console, PageSpeed Insights, and AdSense
through a guided setup. No theme code required.

**FAT Agent recommendation:** If analytics are missing entirely, recommend
Site Kit for clients who are not comfortable editing theme files. For developers
who want full control, use the enqueue approach above.

### Custom Event Tracking Helpers

Provide a small JS utility for tracking custom events without inline scripts
scattered throughout templates:

```php
// Enqueue the event tracking helper
add_action('wp_enqueue_scripts', 'fat_enqueue_event_tracker');
function fat_enqueue_event_tracker() {
    if (is_user_logged_in()) {
        return;
    }

    wp_enqueue_script(
        'fat-event-tracker',
        get_template_directory_uri() . '/assets/js/event-tracker.js',
        ['google-gtag'],
        wp_get_theme()->get('Version'),
        ['strategy' => 'defer', 'in_footer' => true]
    );
}
```

```js
// assets/js/event-tracker.js
(function () {
    'use strict';

    // Track all clicks on elements with data-track-event attribute
    // Usage: <a href="/pricing" data-track-event="cta_click" data-track-label="hero">
    document.addEventListener('click', function (e) {
        var el = e.target.closest('[data-track-event]');
        if (!el) return;

        var eventName = el.getAttribute('data-track-event');
        var eventLabel = el.getAttribute('data-track-label') || '';

        if (typeof gtag === 'function') {
            gtag('event', eventName, {
                event_category: 'engagement',
                event_label: eventLabel,
            });
        }
    });

    // Track scroll depth at 25%, 50%, 75%, 100%
    var scrollMarks = [25, 50, 75, 100];
    var firedMarks = {};

    window.addEventListener('scroll', function () {
        var scrollPercent = Math.round(
            (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
        );

        scrollMarks.forEach(function (mark) {
            if (scrollPercent >= mark && !firedMarks[mark]) {
                firedMarks[mark] = true;
                if (typeof gtag === 'function') {
                    gtag('event', 'scroll_depth', {
                        event_category: 'engagement',
                        event_label: mark + '%',
                        value: mark,
                    });
                }
            }
        });
    });
})();
```

---

## Common Pitfalls

### 1. Enqueuing Scripts Directly Instead of wp_enqueue_script

**Wrong:**
```php
add_action('wp_head', function () {
    echo '<script src="https://cdn.example.com/library.js"></script>';
    echo '<link rel="stylesheet" href="' . get_template_directory_uri() . '/custom.css">';
});
```

**Why it breaks:** Caching plugins cannot optimize these assets. Other plugins
cannot detect or deduplicate them. Defer/async strategies do not apply. The
script may load before its dependencies.

**Right:**
```php
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script('external-library', 'https://cdn.example.com/library.js', [], null, ['strategy' => 'defer', 'in_footer' => true]);
    wp_enqueue_style('theme-custom', get_template_directory_uri() . '/custom.css', [], wp_get_theme()->get('Version'));
});
```

### 2. Not Escaping Output (XSS Risk)

**Wrong:**
```php
<h1><?php echo $title; ?></h1>
<a href="<?php echo $url; ?>">Link</a>
<img alt="<?php echo $alt; ?>">
```

**Right:**
```php
<h1><?php echo esc_html($title); ?></h1>
<a href="<?php echo esc_url($url); ?>">Link</a>
<img alt="<?php echo esc_attr($alt); ?>">
```

WordPress escaping functions:
| Function | Use Case |
|----------|----------|
| `esc_html()` | Output inside HTML elements |
| `esc_attr()` | Output inside HTML attributes |
| `esc_url()` | Output as a URL (href, src) |
| `esc_js()` | Output inside inline JavaScript |
| `esc_textarea()` | Output inside `<textarea>` |
| `wp_kses_post()` | Allow safe HTML (post content) |

### 3. Plugin Conflicts with Theme Features

When a theme and plugin both try to handle the same thing (e.g., both add
JSON-LD, both modify the title tag):

```php
// Always check if a plugin handles the feature first
function fat_has_seo_plugin() {
    return defined('WPSEO_VERSION') || defined('RANK_MATH_VERSION') || defined('AIOSEO_VERSION');
}

// Guard your theme's SEO output
add_action('wp_head', 'fat_theme_seo_output');
function fat_theme_seo_output() {
    if (fat_has_seo_plugin()) {
        return;
    }
    // Your theme's fallback SEO output
}
```

### 4. Not Using a Child Theme

Editing a parent theme's files directly means all changes are lost on the
next theme update.

Minimum child theme structure:
```
mytheme-child/
  style.css      (required -- with Template: header pointing to parent)
  functions.php  (required -- for adding hooks and filters)
```

```css
/* style.css */
/*
Theme Name:  My Theme Child
Template:    parent-theme-slug
Version:     1.0.0
*/
```

```php
// functions.php
<?php
// Enqueue parent and child styles
add_action('wp_enqueue_scripts', 'child_enqueue_styles');
function child_enqueue_styles() {
    wp_enqueue_style('parent-style', get_template_directory_uri() . '/style.css');
    wp_enqueue_style('child-style', get_stylesheet_uri(), ['parent-style']);
}
```

### 5. Hardcoded URLs

**Wrong:**
```php
<img src="/wp-content/themes/mytheme/images/logo.png">
<a href="https://example.com/about">About</a>
<link rel="stylesheet" href="https://example.com/wp-content/themes/mytheme/style.css">
```

**Right:**
```php
<img src="<?php echo esc_url(get_template_directory_uri() . '/images/logo.png'); ?>">
<a href="<?php echo esc_url(home_url('/about')); ?>">About</a>
// Stylesheets should use wp_enqueue_style, not hardcoded <link> tags
```

Key URL functions:
| Function | Returns |
|----------|---------|
| `home_url('/')` | `https://example.com/` |
| `site_url('/')` | `https://example.com/` (WordPress install URL, may differ) |
| `get_template_directory_uri()` | Parent theme URL |
| `get_stylesheet_directory_uri()` | Child theme URL (or parent if no child) |
| `get_template_directory()` | Parent theme filesystem path |
| `wp_upload_dir()` | Uploads directory path and URL |

### 6. Missing Text Domain for Translations

**Wrong:**
```php
echo 'Read More';
echo "Posted by $author";
```

**Right:**
```php
echo esc_html__('Read More', 'theme-textdomain');
printf(esc_html__('Posted by %s', 'theme-textdomain'), esc_html($author));
```

Translation functions:
| Function | Purpose |
|----------|---------|
| `__('text', 'domain')` | Return translated string |
| `_e('text', 'domain')` | Echo translated string |
| `esc_html__()` | Return translated + HTML-escaped |
| `esc_html_e()` | Echo translated + HTML-escaped |
| `_n()` | Singular/plural |
| `_x()` | Translated with context |

### 7. SQL Injection via Unsanitized Database Queries

**Wrong:**
```php
global $wpdb;
$results = $wpdb->get_results(
    "SELECT * FROM {$wpdb->posts} WHERE post_title LIKE '%{$_GET['search']}%'"
);
```

**Right:**
```php
global $wpdb;
$search  = sanitize_text_field($_GET['search'] ?? '');
$results = $wpdb->get_results(
    $wpdb->prepare(
        "SELECT * FROM {$wpdb->posts} WHERE post_title LIKE %s",
        '%' . $wpdb->esc_like($search) . '%'
    )
);
```

Always use `$wpdb->prepare()` for any query that includes user input. Use
`$wpdb->esc_like()` when building LIKE clauses. Better yet, use `WP_Query`
or `get_posts()` instead of direct database queries whenever possible -- they
handle sanitization and caching automatically.

---

## Quick Diagnosis Reference

When FAT Agent finds an issue, use this table to identify the likely cause
and the section above that covers the fix.

| FAT Agent Finding | Likely Cause | Fix Section |
|-------------------|-------------|-------------|
| Missing `<title>` | Theme hardcodes title or lacks `title-tag` support | SEO Meta Tags |
| Missing meta description | No SEO plugin, no manual meta | SEO Meta Tags |
| Missing Open Graph tags | No SEO plugin, no manual OG output | SEO Meta Tags |
| No JSON-LD / structured data | Not implemented | Structured Data |
| Images missing `srcset` | Using raw `<img>` instead of WP image functions | Image Optimization |
| No `loading="lazy"` | Theme overrides or old WP version | Image Optimization |
| No skip link | Missing from `header.php` | Accessibility |
| Missing `lang` attribute | Theme `header.php` uses `<html>` without `language_attributes()` | Accessibility |
| Forms missing labels | Plugin or theme form without `<label>` | Accessibility |
| Render-blocking scripts | Scripts enqueued without defer/async | Performance |
| Large unused CSS | Plugin CSS loaded on every page | Performance |
| No analytics detected | Not installed | Analytics |
| Mixed content | Hardcoded HTTP URLs in theme | Common Pitfalls |
