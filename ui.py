import rumps
from core.manager import TaskManager
from core.db import init_db

class GearboxApp(rumps.App):
    def __init__(self):
        super(GearboxApp, self).__init__("Gearbox", icon=None)
        self.menu = ["Loading..."]
        init_db()
        self.refresh_timer = rumps.Timer(self.refresh_menu, 5)
        self.refresh_timer.start()
        self.refresh_menu(None)

    def refresh_menu(self, sender):
        try:
            tasks = TaskManager.get_tasks()
            recent_runs = TaskManager.get_recent_runs(limit=10)
        except Exception as e:
            self.title = "⚙️⚠️"
            self.menu.clear()
            self.menu.update([rumps.MenuItem(f"Error: {e}")])
            return

        # Check overall health (if any recent run failed among top 3)
        has_failures = any(r['status'] == 'failed' for r in recent_runs[:3])
        if has_failures:
            self.title = "⚙️🔴"
        else:
            self.title = "⚙️🟢"

        menu_items = []
        
        # Upcoming Tasks
        menu_items.append(rumps.MenuItem("--- Active Tasks ---"))
        if not tasks:
            menu_items.append(rumps.MenuItem("No tasks configured"))
        
        for task in tasks:
            status_symbol = "⏸️" if task["is_paused"] else "🏃"
            title = f"{status_symbol} {task['name']} ({task['schedule']})"
            item = rumps.MenuItem(title)
            
            # Setup callback to pause/resume
            item.set_callback(self.toggle_task_status)
            item.task_name = task["name"]
            item.is_paused = bool(task["is_paused"])
            menu_items.append(item)

        menu_items.append(rumps.separator)
        menu_items.append(rumps.MenuItem("--- Recent Runs ---"))
        
        if not recent_runs:
            menu_items.append(rumps.MenuItem("No recent runs"))
        else:
            for r in recent_runs[:5]:
                symbol = "✅" if r["status"] == "success" else ("❌" if r["status"] == "failed" else "⏳")
                time_str = r["started_at"].split("T")[1][:5] if "T" in r["started_at"] else str(r["started_at"])
                title = f"{symbol} {r['task_name']} ({time_str})"
                menu_items.append(rumps.MenuItem(title))

        menu_items.append(rumps.separator)
        quit_button = rumps.MenuItem("Quit Gearbox UI")
        quit_button.set_callback(rumps.quit_application)
        menu_items.append(quit_button)
        
        self.menu.clear()
        self.menu.update(menu_items)

    def toggle_task_status(self, sender):
        new_state = not sender.is_paused
        TaskManager.set_pause_status(sender.task_name, new_state)
        self.refresh_menu(None)

if __name__ == '__main__':
    app = GearboxApp()
    app.run()
