#!/bin/sh
# Compiles the corpus into bin/. Subprograms as modules, steps as executables.
set -e
cd "$(dirname "$0")/.."
mkdir -p bin
./tools/collint.sh src/*.cbl tools/*.cbl copybooks/*.cpy
for m in NAMCTL DATCNV PENACC DATECNV; do
    cobc -m -std=ibm -I copybooks/ "src/$m.cbl" -o "bin/$m"
done
cobc -x -std=ibm -I copybooks/ tools/BLDFIX.cbl -o bin/BLDFIX
for p in ENTVAL DUPCHK STATCALC FTDCALC PENCALC ESTPEN FRZEVAL \
         OVPINT OFFSET CAWRMTCH NOTGEN; do
    cobc -x -std=ibm -I copybooks/ "src/$p.cbl" -o "bin/$p"
done
echo "build complete"
