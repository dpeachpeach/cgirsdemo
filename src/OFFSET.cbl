       IDENTIFICATION DIVISION.
       PROGRAM-ID. OFFSET.
      *****************************************************************
      *    REFUND OFFSET - IRM 21.4.6                                 *
      *    STEP 090.  OUTSTANDING LIABILITIES ARE SATISFIED IN        *
      *    SOURCE ORDER BMF, IMF, THEN DMF (TOP) LAST.                *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODINT.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT DBTIN  ASSIGN TO "data/DEBTS.txt"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT MODOT  ASSIGN TO "data/MODOFF.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS3.
           SELECT OFRPT  ASSIGN TO "data/OFFSET.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  DBTIN.
       01  DBTIN-REC               PIC X(39).
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  OFRPT.
       01  OFRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  FS3                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  DEOF                    PIC X VALUE "N".
       01  G1                      PIC 9(6) VALUE ZERO.
       01  G2                      PIC 9(6) VALUE ZERO.
       01  G3                      PIC 9(6) VALUE ZERO.
       01  G4                      PIC 9(6) VALUE ZERO.
       01  NDBT                    PIC S9(4) COMP VALUE ZERO.
       01  DX                      PIC S9(4) COMP.
       01  PX                      PIC S9(4) COMP.
       01  AVAIL                   PIC S9(11)V99 COMP-3.
       01  LIA                     PIC S9(11)V99 COMP-3.
       01  APPL                    PIC S9(11)V99 COMP-3.
       01  PRISRC                  PIC X(2).
       01  DBTREC.
           05  DB-EIN              PIC 9(09).
           05  DB-SRC              PIC X(02).
           05  DB-MFT              PIC 9(02).
           05  DB-TXPD             PIC 9(06).
           05  DB-AMT              PIC 9(11)V99.
           05  DB-DT               PIC 9(07).
       01  DBTTAB.
           05  DT-ENT OCCURS 500 TIMES.
               10  DT-EIN          PIC 9(09).
               10  DT-SRC          PIC X(02).
               10  DT-MFT          PIC 9(02).
               10  DT-TXPD         PIC 9(06).
               10  DT-BAL          PIC S9(11)V99 COMP-3.
       01  GRPT.
           05  FILLER              PIC X(06) VALUE "OFFSET".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  GR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  GR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  GR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  GR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  GR-TXT              PIC X(24).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  GR-SRC              PIC X(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  GR-AMT              PIC ZZZZZZZZ9.99.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  GR-REM              PIC ZZZZZZZZ9.99.
           05  FILLER              PIC X(20) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-LOAD
           OPEN INPUT MODIN OUTPUT MODOT OFRPT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           CLOSE MODIN MODOT OFRPT
           DISPLAY "OFFSET  READ    " G1
           DISPLAY "OFFSET  WRITTEN " G2
           DISPLAY "OFFSET  APPLIED " G3
           DISPLAY "OFFSET  SUPPRESS" G4
           STOP RUN.
      *
      *    LOAD THE OUTSTANDING LIABILITY FILE INTO CORE.
      *
       1000-LOAD.
           OPEN INPUT DBTIN
           PERFORM UNTIL DEOF = "Y"
               READ DBTIN INTO DBTREC
                   AT END
                       MOVE "Y" TO DEOF
                   NOT AT END
                       IF NDBT < 500
                           ADD 1 TO NDBT
                           MOVE DB-EIN  TO DT-EIN(NDBT)
                           MOVE DB-SRC  TO DT-SRC(NDBT)
                           MOVE DB-MFT  TO DT-MFT(NDBT)
                           MOVE DB-TXPD TO DT-TXPD(NDBT)
                           MOVE DB-AMT  TO DT-BAL(NDBT)
                       END-IF
               END-READ
           END-PERFORM
           CLOSE DBTIN
           DISPLAY "OFFSET  DEBTS   " NDBT.
       2000-PROC.
           READ MODIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO G1
                   PERFORM 2100-OFF THRU 2100-X
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO G2
           END-READ.
       2100-OFF.
           COMPUTE LIA = BMF-ASSD + BMF-PFTD + BMF-PFTF + BMF-PFTP
           COMPUTE AVAIL = BMF-DEP + BMF-CRD + BMF-INT - LIA
           IF AVAIL NOT > ZERO
               GO TO 2100-X
           END-IF
      *
      *    A REFUND OR OFFSET FREEZE STOPS THE MODULE HERE.
      *
           IF BMF-FRZ-O = "O"
               ADD 1 TO G4
               MOVE BMF-EIN TO GR-EIN
               MOVE BMF-MFT TO GR-MFT
               MOVE BMF-TXPD TO GR-TXPD
               MOVE "G901" TO GR-COD
               MOVE "OFFSET FROZEN" TO GR-TXT
               MOVE SPACES TO GR-SRC
               MOVE ZERO TO GR-AMT
               MOVE AVAIL TO GR-REM
               WRITE OFRPT-REC FROM GRPT
               GO TO 2100-X
           END-IF
           PERFORM VARYING PX FROM 1 BY 1 UNTIL PX > 3
               EVALUATE PX
                   WHEN 1
                       MOVE "BM" TO PRISRC
                   WHEN 2
                       MOVE "IM" TO PRISRC
                   WHEN OTHER
                       MOVE "DM" TO PRISRC
               END-EVALUATE
               PERFORM 2200-SCAN
           END-PERFORM.
       2100-X.
           EXIT.
       2200-SCAN.
           PERFORM VARYING DX FROM 1 BY 1 UNTIL DX > NDBT
               IF DT-EIN(DX) = BMF-EIN AND DT-SRC(DX) = PRISRC
                  AND DT-BAL(DX) > ZERO AND AVAIL > ZERO
                   IF DT-BAL(DX) < AVAIL
                       MOVE DT-BAL(DX) TO APPL
                   ELSE
                       MOVE AVAIL TO APPL
                   END-IF
                   SUBTRACT APPL FROM DT-BAL(DX)
                   SUBTRACT APPL FROM AVAIL
                   ADD 1 TO G3
                   MOVE BMF-EIN TO GR-EIN
                   MOVE BMF-MFT TO GR-MFT
                   MOVE BMF-TXPD TO GR-TXPD
                   MOVE "G902" TO GR-COD
                   MOVE "OFFSET APPLIED" TO GR-TXT
                   MOVE PRISRC TO GR-SRC
                   MOVE APPL TO GR-AMT
                   MOVE AVAIL TO GR-REM
                   WRITE OFRPT-REC FROM GRPT
               END-IF
           END-PERFORM.
