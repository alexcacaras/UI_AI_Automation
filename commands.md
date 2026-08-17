1. click N -> N represents the index number for the perception, click is to click what that number represents

2. type N text -> N represents the index number for the perception, type is to type into what that number represents, replace N with the number and text with what you have to type

3. type N text Enter -> N represents the index number for the perception, type is to type into what that number represents, Enter is to press the button on keyboard Enter it always goes at end of this command, replace N with the number and text with what you have to type

4. nav URL -> nav is to navigate to the URL that is needed to go to, replace URL with the url you need to go to

5. 5. press KEY -> presses a keyboard key on whatever is currently focused (no index). 
   Capitalize key names. Examples: press Enter, press Escape, press Control+A
   (Tip: click or type into a field first to focus it, THEN press on the next command.)
   Optionally add a number to repeat the press, e.g. press PageDown 3 presses
   PageDown three times. Most useful for scrolling (PageDown / PageUp).

    List of commands KEY could be:
    KEY: Enter, Escape, Tab, Backspace, Control+A, Control+C, Control+V, ArrowDown, ArrowUp, ArrowLeft, ArrowRight, PageDown, PageUp

6. done -> done finishes the loop and the run 


7. wait -> pauses ~3 seconds then re-perceives. Use when the page looks half-loaded 
   or when no useful option appears yet (Redwood still rendering).

8. fill <field name> | <value> -> Fill a form field BY ITS NAME (not index).
   Use for text boxes and dropdowns. The field name is the "name" in the element
   list. Separate name and value with a pipe | . Quotes around the name are optional (both work).
   For dropdowns, fill auto-selects the matching option — no separate press Enter needed.
   Examples:
     fill Department | Mathematics
     fill What's the reason for this request? | New Position

9. scroll <page|table> <amount> -> Scrolls to reveal elements not currently visible.
   Elements below the fold are NOT in the element list — they have no index and cannot
   be clicked until scrolled into view. Scroll first, then act on the new list.
     page  = scrolls the whole browser window (use for long forms)
     table = scrolls an inner data grid / results table (use when a table has more rows)
   Amount is pixels. NEGATIVE scrolls UP. Amount is optional (default 600).
   Examples:
     scroll page 600      (down one screenful)
     scroll page -600     (back up)
     scroll table 400     (more rows in the results table)

10. select N value -> Choose an option from a NATIVE dropdown (a <select> element).
    N is the index number from the element list; the element's tag must be "select".
    `value` is the visible option text to choose, exactly as it appears in the dropdown.
    Use this for standard OS dropdowns (Country, State, Purpose, etc.) — NOT for
    Oracle's type-to-filter comboboxes (use type/fill for those).
    The value can contain spaces; write it plainly after the index.
    Examples:
      select 56 Sold to
      select 12 Canada
      select 8 Bill to