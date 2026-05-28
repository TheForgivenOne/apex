from apex import Apex, live

app = Apex()


class Counter(live.Component):
    def init(self):
        self.count = 0

    def render(self):
        return f"""
        <div id="c{self.id}" class="card" style="text-align:center;">
            <h2>Live Counter</h2>
            <div style="font-size:3rem;font-weight:bold;margin:1rem 0;color:#0070f3;">
                {self.count}
            </div>
            <div style="display:flex;gap:0.5rem;justify-content:center;">
                <button hx-post="{self.url_for('decrement')}"
                        hx-target="#c{self.id}"
                        hx-swap="outerHTML">-1</button>
                <button hx-post="{self.url_for('reset')}"
                        hx-target="#c{self.id}"
                        hx-swap="outerHTML"
                        style="background:#666;">Reset</button>
                <button hx-post="{self.url_for('increment')}"
                        hx-target="#c{self.id}"
                        hx-swap="outerHTML">+1</button>
            </div>
            <p class="badge" style="margin-top:1rem;">Component: {self.id}</p>
        </div>
        """

    def increment(self, request):
        self.count += 1

    def decrement(self, request):
        self.count -= 1

    def reset(self, request):
        self.count = 0


app.live("/counter", Counter, title="Apex Counter")


class TodoList(live.Component):
    def init(self):
        self.todos = [
            {"id": 1, "text": "Learn Apex", "done": True},
            {"id": 2, "text": "Build live components", "done": False},
            {"id": 3, "text": "Ship to production", "done": False},
        ]
        self.next_id = 4
        self.filter = "all"

    def render(self):
        filtered = self.todos
        if self.filter == "active":
            filtered = [t for t in self.todos if not t["done"]]
        elif self.filter == "completed":
            filtered = [t for t in self.todos if t["done"]]

        items = ""
        for todo in filtered:
            done_class = "style=\"text-decoration:line-through;color:#999;\"" if todo["done"] else ""
            items += f"""
            <div id="todo-{todo['id']}" style="display:flex;align-items:center;gap:0.5rem;padding:0.5rem 0;">
                <input type="checkbox" {'checked' if todo['done'] else ''}
                       hx-post="{self.url_for('toggle')}"
                       hx-vals='{{"id": {todo["id"]}}}'
                       hx-target="#todo-list"
                       hx-swap="outerHTML">
                <span {done_class}>{todo['text']}</span>
                <button hx-post="{self.url_for('delete')}"
                        hx-vals='{{"id": {todo["id"]}}}'
                        hx-target="#todo-list"
                        hx-swap="outerHTML"
                        style="margin-left:auto;padding:0.25rem 0.5rem;font-size:0.8rem;background:#e00;">
                    x
                </button>
            </div>"""

        active_count = len([t for t in self.todos if not t["done"]])

        return f"""
        <div id="todo-list" class="card">
            <h2>Live Todo List</h2>
            <div style="display:flex;gap:0.5rem;margin-bottom:1rem;">
                <input id="new-todo-text" name="text" placeholder="Add a todo..."
                       style="flex:1;"
                       hx-on:keydown="if(event.key==='enter') document.getElementById('add-btn').click()">
                <button id="add-btn"
                        hx-post="{self.url_for('add')}"
                        hx-include="#new-todo-text"
                        hx-target="#todo-list"
                        hx-swap="outerHTML"
                        hx-on::after-request="document.getElementById('new-todo-text').value=''">
                    Add
                </button>
            </div>
            <div style="margin-bottom:0.5rem;">
                <span class="badge">{active_count} items left</span>
            </div>
            <div style="margin-bottom:0.5rem;display:flex;gap:0.5rem;">
                <button hx-get="{self.url_for('filter_all')}"
                        hx-target="#todo-list" hx-swap="outerHTML"
                        style="{'background:#0070f3' if self.filter=='all' else 'background:#999;'}">All</button>
                <button hx-get="{self.url_for('filter_active')}"
                        hx-target="#todo-list" hx-swap="outerHTML"
                        style="{'background:#0070f3' if self.filter=='active' else 'background:#999;'}">Active</button>
                <button hx-get="{self.url_for('filter_completed')}"
                        hx-target="#todo-list" hx-swap="outerHTML"
                        style="{'background:#0070f3' if self.filter=='completed' else 'background:#999;'}">Completed</button>
            </div>
            <div>{items}</div>
        </div>"""

    async def add(self, request):
        form = await request.form()
        text = form.get("text", "")
        if text.strip():
            self.todos.append({"id": self.next_id, "text": text.strip(), "done": False})
            self.next_id += 1

    async def toggle(self, request):
        form = await request.form()
        todo_id = int(form.get("id", 0))
        for todo in self.todos:
            if todo["id"] == todo_id:
                todo["done"] = not todo["done"]
                break

    async def delete(self, request):
        form = await request.form()
        todo_id = int(form.get("id", 0))
        self.todos = [t for t in self.todos if t["id"] != todo_id]

    def filter_all(self, request):
        self.filter = "all"

    def filter_active(self, request):
        self.filter = "active"

    def filter_completed(self, request):
        self.filter = "completed"


app.live("/todos", TodoList, title="Apex Todos")


@app.get("/")
async def home(request):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Apex Framework</title>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               max-width: 800px; margin: 0 auto; padding: 2rem; color: #333; line-height: 1.6; }}
        h1 {{ margin-bottom: 1rem; }}
        .card {{ background: #f5f5f5; padding: 1.5rem; border-radius: 8px; margin: 1rem 0; }}
        a {{ color: #0070f3; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .demo-link {{ display: block; padding: 1rem; background: #0070f3; color: white;
                     border-radius: 8px; margin: 1rem 0; font-size: 1.2rem; text-align: center; }}
        .demo-link:hover {{ background: #005bb5; text-decoration: none; }}
    </style>
</head>
<body>
    <h1>Apex Live Components</h1>
    <p style="margin-bottom:2rem;">Interactive Python components with automatic HTMX wiring. No JavaScript required.</p>
    <a class="demo-link" href="/counter">Live Counter Demo</a>
    <a class="demo-link" href="/todos" style="background:#28a745;">Live Todo List Demo</a>
    <div class="card">
        <h2>How it works</h2>
        <pre style="background:#1e1e1e;color:#d4d4d4;padding:1rem;border-radius:4px;margin-top:0.5rem;overflow-x:auto;">
class Counter(live.Component):
    def init(self):
        self.count = 0

    def render(self):
        return f'''&lt;div id="c{{self.id}}"&gt;
            Count: {{self.count}}
            &lt;button hx-post="{{self.url_for('increment')}}"
                    hx-target="#c{{self.id}}"&gt;
                +1
            &lt;/button&gt;
        &lt;/div&gt;'''

    def increment(self, request):
        self.count += 1

app.live("/counter", Counter)
        </pre>
    </div>
</body>
</html>"""


@app.get("/favicon.ico")
async def favicon(request):
    from apex import Response
    return Response(status=204)


if __name__ == "__main__":
    app.serve()
