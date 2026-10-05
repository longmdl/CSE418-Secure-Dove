#!/bin/bash

if grep -R -n "innerHTML\|outerHTML\|insertAdjacentHTML\|document.write" public/js; then
    echo "Unsafe HTML rendering method found in public/js. Please fix!"
    exit 1
fi
echo "Safe HTML rendering used. Good job!"
exit 0
