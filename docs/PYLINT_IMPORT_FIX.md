# Pylint Fix: Import Order Issues

## Date: October 19, 2025

## Issues Found by Pylint

### Issue 1: Wrong Import Order (netbox_filters.py)

```
C0411: standard import "import sys" should be placed before local imports (wrong-import-order)
C0411: standard import "import os" should be placed before local imports (wrong-import-order)
```

**Problem:** Standard library imports (`sys`, `os`) were placed after local module imports.

**PEP 8 Import Order:**

1. Standard library imports
2. Related third-party imports
3. Local application/library-specific imports

### Issue 2: Import Outside Toplevel (vlan_filters.py)

```
C0415: Import outside toplevel (re) (import-outside-toplevel)
```

**Problem:** `import re` was inside the `parse_evpn_evi_output()` function.

**Best Practice:** Imports should be at module level unless there's a specific reason (lazy loading, circular imports, optional dependencies).

## Fixes Applied

### Fix 1: Reorganize Import Order in netbox_filters.py

**Before:**

```python
#!/usr/bin/env python3
"""
Custom Ansible filters for NetBox data transformation
"""

from netbox_filters_lib.ospf_filters import (...)
from netbox_filters_lib.comparison import (...)
# ... more local imports ...
import sys  # ❌ Standard library after local imports
import os   # ❌ Standard library after local imports

_filter_dir = os.path.dirname(os.path.abspath(__file__))
```

**After:**

```python
#!/usr/bin/env python3
"""
Custom Ansible filters for NetBox data transformation
"""

import sys  # ✅ Standard library first
import os   # ✅ Standard library first

# Add the filter_plugins directory to Python path
_filter_dir = os.path.dirname(os.path.abspath(__file__))
if _filter_dir not in sys.path:
    sys.path.insert(0, _filter_dir)

# Import from the netbox_filters_lib package (subdirectory)
# These imports must come after sys.path manipulation above
# pylint: disable=wrong-import-position
# flake8: noqa: E402
from netbox_filters_lib.utils import collapse_vlan_list, select_interfaces_to_configure
from netbox_filters_lib.vlan_filters import (...)
# ... more local imports ...
```

### Fix 2: Move re Import to Module Level in vlan_filters.py

**Before:**

```python
#!/usr/bin/env python3
"""
VLAN-related filters for NetBox data transformation
"""

from .utils import _debug


def parse_evpn_evi_output(output):
    """Parse 'show evpn evi' command output"""
    import re  # ❌ Import inside function

    vnis = re.findall(pattern, output, re.MULTILINE)
    # ...
```

**After:**

```python
#!/usr/bin/env python3
"""
VLAN-related filters for NetBox data transformation
"""

import re  # ✅ Import at module level

from .utils import _debug


def parse_evpn_evi_output(output):
    """Parse 'show evpn evi' command output"""
    # No import here anymore

    vnis = re.findall(pattern, output, re.MULTILINE)
    # ...
```

## Why These Changes Matter

### Import Order

- **Readability:** Consistent import ordering makes code easier to scan
- **Standards:** Follows PEP 8 style guide
- **Tool Compatibility:** Allows linters and formatters to work correctly
- **Convention:** Matches Python community best practices

### Toplevel Imports

- **Performance:** Module-level imports are executed once at import time, not on every function call
- **Clarity:** Makes dependencies explicit at the top of the file
- **Debugging:** Easier to see what modules are required
- **Testing:** Simpler to mock imports in tests

## Exception: Why Local Imports After sys.path?

In `netbox_filters.py`, we intentionally import local modules **after** manipulating `sys.path`:

```python
import sys
import os

# Modify sys.path first
_filter_dir = os.path.dirname(os.path.abspath(__file__))
if _filter_dir not in sys.path:
    sys.path.insert(0, _filter_dir)

# pylint: disable=wrong-import-position  # ← This tells pylint it's intentional
from netbox_filters_lib.vlan_filters import (...)
```

**Why:** The local imports depend on the sys.path modification to work when the role is installed. This is a valid exception to the rule, which is why we use `# pylint: disable=wrong-import-position`.

## Verification

### Test Import Order

```bash
cd /workspaces/ansible-role-aruba-cx-switch
python3 -c "import sys; sys.path.insert(0, 'filter_plugins'); from netbox_filters import FilterModule; print('✅ Imports work correctly')"
```

### Test Filter Functionality

```bash
python3 -c "
import sys
sys.path.insert(0, 'filter_plugins')
from netbox_filters_lib.vlan_filters import parse_evpn_evi_output

output = '''L2VNI : 10100010
    VLAN : 10'''

result = parse_evpn_evi_output(output)
assert result['evpn_vlans'] == [10]
print('✅ Filter works after import fix')
"
```

### Run Pylint

```bash
cd /workspaces/ansible-role-aruba-cx-switch
pylint filter_plugins/netbox_filters.py filter_plugins/netbox_filters_lib/vlan_filters.py
```

**Expected:** No errors related to import order or import-outside-toplevel

## Files Modified

1. **filter_plugins/netbox_filters.py**

    - Moved `import sys` and `import os` to top of file (before local imports)
    - Kept local imports after sys.path manipulation with proper pylint directive

2. **filter_plugins/netbox_filters_lib/vlan_filters.py**

    - Moved `import re` from inside `parse_evpn_evi_output()` to module level
    - Placed after standard docstring, before local imports

## Checklist

- [x] Standard library imports before local imports
- [x] No imports inside functions (except when absolutely necessary)
- [x] Proper pylint directives for intentional exceptions
- [x] All filters still work correctly
- [x] No pylint errors

## Related Standards

- **PEP 8:** [Import Formatting](https://peps.python.org/pep-0008/#imports)
- **Pylint:** [Import Order Checker](https://pylint.pycqa.org/en/latest/user_guide/messages/convention/wrong-import-order.html)
- **Google Python Style Guide:** [Imports Section](https://google.github.io/styleguide/pyguide.html#313-imports-formatting)

---

**Status:** Fixed ✅
**Pylint:** Passing
**Last Updated:** October 19, 2025
