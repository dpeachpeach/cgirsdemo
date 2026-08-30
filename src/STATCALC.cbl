       IDENTIFICATION DIVISION.
       PROGRAM-ID. STATCALC.
      *****************************************************************
      *    STATUTE DATE COMPUTATION - ASED / RSED / CSED              *
      *    STEP 030.  CALLS DATCNV FOR JULIAN CONVERSION.             *
      *    W8 POS 1-2 CARRIES THE STATUTE CONDITION CODE.             *
      *    CODES 05/07/12 ONLY. 09 AND 11 WITHDRAWN 06/88.            *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODDUP.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT MODOT  ASSIGN TO "data/MODSTAT.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT STRPT  ASSIGN TO "data/STATCALC.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  STRPT.
       01  STRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  R1                      PIC 9(6) VALUE ZERO.
       01  R2                      PIC 9(6) VALUE ZERO.
       01  R6                      PIC 9(6) VALUE ZERO.
       01  R7                      PIC 9(6) VALUE ZERO.
       01  SY                      PIC 9(4).
       01  SM                      PIC 9(2).
       01  SDY                      PIC 9(2).
       01  SCC                     PIC 9(2).
       01  SDT                     PIC 9(8).
       01  W7RD                    PIC 9(7).
       01  W7AS                   PIC 9(7).
       01  W7RS                   PIC 9(7).
       01  W7CS                   PIC 9(7).
       01  W7YR                     PIC 9(4).
       01  DC-PARM.
           05  DCP-FUNC            PIC X(01).
           05  DCP-GREG            PIC 9(08).
           05  DCP-JUL             PIC 9(07).
           05  DCP-RC              PIC X(01).
           05  DCP-RSV             PIC X(07).
       01  SRPT.
           05  FILLER              PIC X(08) VALUE "STATCALC".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  SR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  SR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  SR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  SR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  SR-TXT              PIC X(34).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  SR-ASED             PIC 9(07).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  SR-CSED             PIC 9(07).
           05  FILLER              PIC X(30) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN OUTPUT MODOT STRPT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           CLOSE MODIN MODOT STRPT
           DISPLAY "STATCALC READ   " R1
           DISPLAY "STATCALC WRITTEN" R2
           DISPLAY "STATCALC 6YR    " R6
           DISPLAY "STATCALC SUSPEND" R7
           STOP RUN.
       2000-PROC.
           READ MODIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO R1
                   PERFORM 2100-CALC
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO R2
           END-READ.
       2100-CALC.
           MOVE BMF-W8(1:2) TO SCC
           PERFORM 2200-RDD
           PERFORM 2300-ASED
           PERFORM 2400-RSED
           PERFORM 2500-CSED
           MOVE W7AS TO BMF-ASED
           MOVE W7RS TO BMF-RSED
           MOVE W7CS TO BMF-CSED.
       2200-RDD.
           MOVE BMF-TXPD(1:4) TO SY
           MOVE BMF-TXPD(5:2) TO SM
           EVALUATE BMF-MFT
               WHEN 01
                   ADD 1 TO SM
                   IF SM > 12
                       SUBTRACT 12 FROM SM
                       ADD 1 TO SY
                   END-IF
                   MOVE 28 TO SDY
               WHEN 02
                   ADD 4 TO SM
                   IF SM > 12
                       SUBTRACT 12 FROM SM
                       ADD 1 TO SY
                   END-IF
                   MOVE 15 TO SDY
               WHEN OTHER
                   ADD 1 TO SY
                   MOVE 01 TO SM
                   MOVE 31 TO SDY
           END-EVALUATE
           COMPUTE SDT = SY * 10000 + SM * 100 + SDY
           MOVE "J" TO DCP-FUNC
           MOVE SDT TO DCP-GREG
           CALL "DATCNV" USING DC-PARM
           MOVE DCP-JUL TO W7RD.
       2300-ASED.
           COMPUTE W7YR = SY + 3
           COMPUTE W7AS = W7YR * 1000 + FUNCTION MOD(W7RD 1000)
           PERFORM 2350-SPCL.
       2350-SPCL.
           EVALUATE SCC
               WHEN 05
                   COMPUTE W7YR = SY + 6
                   COMPUTE W7AS = W7YR * 1000
                       + FUNCTION MOD(W7RD 1000)
                   ADD 1 TO R6
                   MOVE "S301" TO SR-COD
                   MOVE "25 PCT OMISSION - 6 YEAR ASED" TO SR-TXT
                   PERFORM 8000-RPT
               WHEN 07
                   MOVE 9999365 TO W7AS
                   ADD 1 TO R7
                   MOVE "S302" TO SR-COD
                   MOVE "FRAUD - ASED NOT LIMITED" TO SR-TXT
                   PERFORM 8000-RPT
               WHEN 12
                   COMPUTE W7YR = SY + 3
                   MOVE BMF-W8(4:5) TO DCP-RSV(1:5)
                   COMPUTE W7AS = W7YR * 1000 + 105
                   ADD 1 TO R7
                   MOVE "S303" TO SR-COD
                   MOVE "FORM 872 CONSENT - ASED EXTENDED" TO SR-TXT
                   PERFORM 8000-RPT
           END-EVALUATE.
       2400-RSED.
           COMPUTE W7YR = SY + 3
           COMPUTE W7RS = W7YR * 1000 + FUNCTION MOD(W7RD 1000)
           IF BMF-DEP > ZERO
               COMPUTE W7YR = SY + 2
               IF (W7YR * 1000) > W7RS
                   COMPUTE W7RS = W7YR * 1000
                       + FUNCTION MOD(W7RD 1000)
               END-IF
           END-IF.
       2500-CSED.
           COMPUTE W7YR = SY + 10
           COMPUTE W7CS = W7YR * 1000 + FUNCTION MOD(W7RD 1000)
           IF BMF-FRZ-V = "V" OR BMF-FRZ-Z = "Z"
               ADD 183 TO W7CS
               IF FUNCTION MOD(W7CS 1000) > 365
                   ADD 1000 TO W7CS
                   SUBTRACT 365 FROM W7CS
               END-IF
               ADD 1 TO R7
               MOVE "S304" TO SR-COD
               MOVE "CSED SUSPENDED - BANKRUPTCY" TO SR-TXT
               PERFORM 8000-RPT
           END-IF.
       8000-RPT.
           MOVE BMF-EIN TO SR-EIN
           MOVE BMF-MFT TO SR-MFT
           MOVE BMF-TXPD TO SR-TXPD
           MOVE W7AS TO SR-ASED
           MOVE W7CS TO SR-CSED
           WRITE STRPT-REC FROM SRPT.
