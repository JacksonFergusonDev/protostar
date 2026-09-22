import questionary

from protostar.cli.prompts import (
    Choice,
    Separator,
    Style,
    checkbox,
    confirm,
    select,
    text,
)


def test_prompts_lazy_choice():
    """Verify that prompts.Choice returns a native questionary Choice instance."""
    choice = Choice("Title", value="val")
    assert isinstance(choice, questionary.Choice)
    assert choice.title == "Title"
    assert choice.value == "val"


def test_prompts_lazy_separator():
    """Verify that prompts.Separator returns a native questionary Separator instance."""
    sep = Separator("--- separator ---")
    assert isinstance(sep, questionary.Separator)


def test_prompts_lazy_style():
    """Verify that prompts.Style returns a native questionary Style instance."""
    st = Style([("qmark", "fg:#ff0000 bold")])
    assert isinstance(st, questionary.Style)


def test_prompts_select(mocker):
    """Verify that select forwards message and choices to questionary and returns answer."""
    mock_question = mocker.MagicMock()
    mock_question.ask.return_value = "selected_item"
    mock_q_select = mocker.patch("questionary.select", return_value=mock_question)

    res = select("Choose an option:", choices=["A", "B"])

    assert res == "selected_item"
    mock_q_select.assert_called_once_with("Choose an option:", choices=["A", "B"])
    mock_question.ask.assert_called_once_with(kbi_msg="")


def test_prompts_confirm(mocker):
    """Verify that confirm forwards parameters to questionary and returns bool."""
    mock_question = mocker.MagicMock()
    mock_question.ask.return_value = True
    mock_q_confirm = mocker.patch("questionary.confirm", return_value=mock_question)

    res = confirm("Are you sure?", default=False)

    assert res is True
    mock_q_confirm.assert_called_once_with("Are you sure?", default=False)
    mock_question.ask.assert_called_once_with(kbi_msg="")


def test_prompts_checkbox(mocker):
    """Verify that checkbox forwards parameters to questionary and returns list."""
    mock_question = mocker.MagicMock()
    mock_question.ask.return_value = ["item1", "item2"]
    mock_q_checkbox = mocker.patch("questionary.checkbox", return_value=mock_question)

    res = checkbox("Select items:", choices=["item1", "item2", "item3"])

    assert res == ["item1", "item2"]
    mock_q_checkbox.assert_called_once_with(
        "Select items:", choices=["item1", "item2", "item3"]
    )
    mock_question.ask.assert_called_once_with(kbi_msg="")


def test_prompts_text(mocker):
    """Verify that text forwards parameters to questionary and returns str."""
    mock_question = mocker.MagicMock()
    mock_question.ask.return_value = "entered text"
    mock_q_text = mocker.patch("questionary.text", return_value=mock_question)

    res = text("Project name:", default="my_project")

    assert res == "entered text"
    mock_q_text.assert_called_once_with("Project name:", default="my_project")
    mock_question.ask.assert_called_once_with(kbi_msg="")
