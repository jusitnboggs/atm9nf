# ATM9 No Frills Fork - TODO List

## Completed Fixes

- [x] **Fix Patchouli Book Error for `rebornstorage:rs_book`**
  - **Issue**: Mod `rebornstorage` had `"use_resource_pack": false` in its Patchouli book definition (`rebornstorage:rs_book`).
  - **Fix Applied**: Overrode `kubejs/data/rebornstorage/patchouli_books/rs_book/book.json` with `"use_resource_pack": true`.
