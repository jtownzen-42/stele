"""Navigation and empty states across the premium shell."""
import pytest
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from stele.db import Database
from stele.settings import Settings

@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local'))
    monkeypatch.setattr('stele.credentials.get_token',lambda:None)
    monkeypatch.setattr('stele.burn.imapi.enumerate_recorders',lambda:[])
    monkeypatch.setattr('stele.burn.imapi.probe',lambda:None)
    from stele.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    db=Database(tmp_path/'db.sqlite')
    settings=Settings(db)
    settings.set_vault(tmp_path/'vault')
    settings.set_staging(tmp_path/'staging')
    w=MainWindow(db,settings,start_worker=False)
    w.show()
    app.processEvents()
    yield w
    w.close()
    db.close()

def test_settings_return_to_same_navigation_page(window):
    window.nav.setCurrentRow(0)
    window._open_settings()
    assert window.stack.currentWidget() is window.settings_scroll
    assert window.page_title.text() == 'Workspace settings'
    window.nav.setCurrentRow(0)
    assert window.stack.currentWidget() is window.discover_page
    assert window.page_title.text() == 'Discover models'
    assert window.worker is None

def test_each_section_keeps_existing_route(window):
    for i,title in enumerate(('Discover models','Download queue','Your archive library','Build an archive','Runtime collection')):
        window.nav.setCurrentRow(i)
        assert window.stack.currentIndex() == i
        assert window.page_title.text() == title

def test_empty_state_tracks_data_without_covering_it(window):
    table=window.discover_page.results
    empty=window.discover_page._empty_states[0]
    assert not empty.label.isHidden()
    table.setRowCount(1)
    table.setItem(0,0,QTableWidgetItem('example/model'))
    assert empty.label.isHidden()
    table.setRowCount(0)
    assert not empty.label.isHidden()

def test_activation_display_shows_free_or_pro(window):
    assert window.edition.text() == 'Free'
    window.db.set_setting('license_status','Studio (Offline)')
    window.update_license_display()
    assert window.edition.text() == 'Free'
    window.db.set_setting('license_status','Pro')
    window.update_license_display()
    assert window.edition.text() == 'Pro'
    assert window.nav_labels() == ['Discover','Queue','Library','Burn','Runtimes']

def test_free_tier_burn_is_blocked_before_any_work(window, monkeypatch):
    shown=[]
    monkeypatch.setattr('stele.ui.pages.burn_page.QMessageBox.information',lambda *a: shown.append(a[2]))
    monkeypatch.setattr('stele.ui.pages.burn_page.burn_directory',lambda *a, **k: pytest.fail('burned without Pro'))
    window.burn_page.burn()
    assert shown and 'Stele Pro' in shown[0]
    assert window.db.list_burns() == []

def test_burn_and_iso_assembly_passes_a_real_workspace_path(window, monkeypatch):
    calls=[]
    def build(out_root, *args, **kwargs):
        calls.append(out_root)
        return []
    monkeypatch.setattr('stele.ui.pages.burn_page.build_disc_set',build)
    page=window.burn_page
    snap={'ids':[], 'include_runtime':False, 'capacity':25_000_000_000}
    assert page._assemble(snap) == []
    assert calls[0].parent == window.settings.burn_work()
    assert calls[0].name


def test_keyboard_routes_from_settings_and_focuses_search(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    app = QApplication.instance()
    window.activateWindow()
    app.processEvents()
    window._open_settings()
    QTest.keyClick(window, Qt.Key_3, Qt.ControlModifier)
    assert window.stack.currentWidget() is window.library_page
    window.discover_page.query.setText('example/model')
    QTest.keyClick(window, Qt.Key_L, Qt.ControlModifier)
    assert window.stack.currentWidget() is window.discover_page
    assert window.discover_page.query.hasFocus()
    assert window.discover_page.query.selectedText() == 'example/model'


def test_large_archive_keeps_summary_compact_and_all_files(window):
    from stele.models import HubFile, RepoDetails
    page = window.discover_page
    details = RepoDetails('example/model', 'abc123', 'main', '', '', '', 'MIT', False,
                          'Example', [HubFile(f'shard-{i}.bin', 1000) for i in range(60)])
    page._show_details(details)
    page.profile.setCurrentText('Full repo')
    assert len(page._plan.files) == 60
    assert page.files.rowCount() == 60
    assert '60 files' in page.preview.text()
    assert 'shard-' not in page.preview.text()
    window.resize(1100, 760)
    QApplication.instance().processEvents()
    assert page.files.height() > 100
    assert page.add_button.isVisibleTo(window)


def test_source_switch_clears_stale_preview_and_matches_access(window, monkeypatch):
    page = window.discover_page
    monkeypatch.setattr('stele.ui.pages.discover.civitai_key_status', lambda: 'Example Civitai status')
    page.title.setText('Old model')
    page.card.setPlainText('Old model card')
    page.source.setCurrentIndex(1)
    assert page.title.text() == 'Archive preview'
    assert not page.card.toPlainText()
    assert page.token_label.text() == 'Example Civitai status'
    assert page.save_token_button.isHidden()
    assert page.clear_token_button.isHidden()
    assert not page.manage_key.isHidden()
    page.source.setCurrentIndex(0)
    assert not page.save_token_button.isHidden()
    assert page.manage_key.isHidden()


def test_settings_save_feedback_and_persistent_footer(window):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QPushButton
    window._open_settings()
    window.resize(1100, 760)
    QApplication.instance().processEvents()
    page = window.settings_page
    save = next(button for button in page.findChildren(QPushButton) if button.text() == 'Save workspace')
    for position in (0, page.sections_scroll.verticalScrollBar().maximum()):
        page.sections_scroll.verticalScrollBar().setValue(position)
        QApplication.instance().processEvents()
        assert window.rect().contains(save.mapTo(window, QPoint(save.width()//2, save.height()//2)))
    page.studio_name.setText('Example Studio')
    save.click()
    assert window.settings.studio_name() == 'Example Studio'
    assert page.feedback.text() == 'Workspace saved.'
