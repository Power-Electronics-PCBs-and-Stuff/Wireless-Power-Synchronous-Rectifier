#!/bin/bash
# crop.sh <pdf> <out.png> <x_mm> <y_mm> <w_mm> <h_mm> [dpi]
D=${7:-400}
pdftoppm -png -r $D -x $(python -c "print(int($3/25.4*$D))") -y $(python -c "print(int($4/25.4*$D))") -W $(python -c "print(int($5/25.4*$D))") -H $(python -c "print(int($6/25.4*$D))") -singlefile "$1" "${2%.png}"
