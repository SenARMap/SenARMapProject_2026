async function loadPosts() {
    const grid = document.getElementById('post-grid');
    try {
        const res = await fetch('posts.json');
        const posts = await res.json();

        if (posts.length === 0) {
            grid.innerHTML = `
                <div class="empty-state">
                    <strong>まだ記事がありません</strong>
                    <p>posts/*.md を作成して build.py を実行してください。</p>
                </div>`;
            return;
        }

        grid.innerHTML = posts.map(post => {
            const thumbHtml = post.thumbnail
                ? `<img class="post-card-thumb" src="${escHtml(post.thumbnail)}" alt="${escHtml(post.title)}">`
                : '';
            const authorHtml = post.author
                ? `<span class="post-author">${escHtml(post.author)}</span>`
                : '';
            return `
                <a class="post-card" href="${escHtml(post.path)}">
                    ${thumbHtml}
                    <div class="post-card-body">
                        <div class="post-card-meta">
                            <time datetime="${escHtml(post.date)}">${formatDateJa(post.date)}</time>
                            ${authorHtml}
                        </div>
                        <div class="post-card-title">${escHtml(post.title)}</div>
                        <div class="post-card-excerpt">${escHtml(post.excerpt)}</div>
                        <div class="post-card-more">続きを読む →</div>
                    </div>
                </a>`;
        }).join('');
    } catch (e) {
        grid.innerHTML = `
            <div class="empty-state">
                <strong>記事を読み込めませんでした</strong>
                <p>build.py を実行して posts.json を生成してください。</p>
            </div>`;
    }
}

function formatDateJa(str) {
    const m = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return str;
    return `${m[1]}年${parseInt(m[2])}月${parseInt(m[3])}日`;
}

function escHtml(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

loadPosts();
