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

def test_existing_activation_display_without_new_tier_claim(window):
    assert window.edition.text() == 'Unactivated'
    window.db.set_setting('license_status','Studio (Offline)')
    window.update_license_display()
    assert window.edition.text() == 'Studio (Offline)'
    assert window.nav_labels() == ['Discover','Queue','Library','Burn','Runtimes']

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
