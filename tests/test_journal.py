from pathlib import Path

from protostar.journal import MutationJournal


def test_journal_create_file(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "new_file.txt"
    
    journal.record_mutation(target)
    target.write_text("hello")
    
    assert target.exists()
    assert target.name in journal.created_paths
    assert target.name in journal.touched_paths
    assert target.name not in journal.mutated_paths
    
    res = journal.rollback()
    assert res.succeeded
    assert not target.exists()

def test_journal_mutate_file(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "existing.txt"
    target.write_text("original")
    
    journal.record_mutation(target)
    target.write_text("mutated")
    
    assert target.read_text() == "mutated"
    assert target.name in journal.mutated_paths
    
    res = journal.rollback()
    assert res.succeeded
    assert target.read_text() == "original"

def test_journal_create_directory(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "new_dir"
    
    journal.record_mutation(target)
    target.mkdir()
    
    assert target.is_dir()
    
    res = journal.rollback()
    assert res.succeeded
    assert not target.exists()

def test_journal_mutate_directory(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "existing_dir"
    target.mkdir()
    
    journal.record_mutation(target)
    # We mutate it by deleting it
    target.rmdir()
    
    assert not target.exists()
    
    res = journal.rollback()
    assert res.succeeded
    assert target.is_dir()

def test_journal_create_then_mutate(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "file.txt"
    
    journal.record_mutation(target)
    target.write_text("first")
    
    # Second mutation shouldn't record the intermediate state
    journal.record_mutation(target)
    target.write_text("second")
    
    assert target.read_text() == "second"
    
    res = journal.rollback()
    assert res.succeeded
    assert not target.exists()

def test_journal_idempotent_rollback(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "file.txt"
    journal.record_mutation(target)
    target.write_text("hello")
    
    res1 = journal.rollback()
    assert res1.succeeded
    assert not target.exists()
    
    # second time does nothing
    res2 = journal.rollback()
    assert res2.succeeded
    assert not target.exists()

def test_journal_cannot_rollback_committed(tmp_path: Path) -> None:
    journal = MutationJournal()
    target = tmp_path / "file.txt"
    journal.record_mutation(target)
    target.write_text("hello")
    
    journal.commit()
    res = journal.rollback()
    
    assert not res.succeeded
    assert target.exists()
