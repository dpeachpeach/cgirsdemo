       IDENTIFICATION DIVISION.
       PROGRAM-ID. CAWRMTCH.
      *****************************************************************
      *    COMBINED ANNUAL WAGE REPORTING MATCH                       *
      *    STEP 100.  SEQUENTIAL MATCH OF THE SSA W-2 TOTALS AGAINST  *
      *    THE POSTED FORM 941 LIABILITY FOR THE SAME EIN AND YEAR.   *
      *    BOTH FILES MUST BE IN EIN/YEAR SEQUENCE.                   *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODOFF.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT W2IN   ASSIGN TO "data/CAWRW2.txt"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT CWRPT  ASSIGN TO "data/CAWRMTCH.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  W2IN.
       01  W2IN-REC                PIC X(44).
       FD  CWRPT.
       01  CWRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  MEOF                    PIC X VALUE "N".
       01  WEOF                    PIC X VALUE "N".
       01  C1                      PIC 9(6) VALUE ZERO.
       01  C2                      PIC 9(6) VALUE ZERO.
       01  C3                      PIC 9(6) VALUE ZERO.
       01  C4                      PIC 9(6) VALUE ZERO.
       01  C5                      PIC 9(6) VALUE ZERO.
       01  MKEY                    PIC X(13).
       01  WKEY                    PIC X(13).
       01  HKEY                    PIC X(13).
       01  LIAB                    PIC S9(11)V99 COMP-3.
       01  NQTR                    PIC 9(3).
       01  DIFF                    PIC S9(11)V99 COMP-3.
       01  TOLR                    PIC S9(11)V99 COMP-3.
       01  W2REC.
           05  W2-EIN              PIC 9(09).
           05  W2-YR               PIC 9(04).
           05  W2-WAGE             PIC 9(11)V99.
           05  W2-WHLD             PIC 9(11)V99.
           05  W2-DOC              PIC 9(05).
       01  HOLD-W2.
           05  HW-WAGE             PIC S9(11)V99 COMP-3.
           05  HW-WHLD             PIC S9(11)V99 COMP-3.
           05  HW-DOC              PIC 9(05).
       01  CRPT.
           05  FILLER              PIC X(08) VALUE "CAWRMTCH".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  CR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  CR-YR               PIC 9(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  CR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  CR-TXT              PIC X(24).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  CR-W2               PIC ZZZZZZZZ9.99.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  CR-941              PIC ZZZZZZZZ9.99.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  CR-DIFF             PIC ZZZZZZZZ9.99-.
           05  FILLER              PIC X(15) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN W2IN OUTPUT CWRPT
           PERFORM 8100-RDMOD
           PERFORM 8200-RDW2
           PERFORM 2000-MATCH
               UNTIL MEOF = "Y" AND WEOF = "Y"
           CLOSE MODIN W2IN CWRPT
           DISPLAY "CAWRMTCH 941 GRP " C1
           DISPLAY "CAWRMTCH W2  REC " C2
           DISPLAY "CAWRMTCH MATCHED " C3
           DISPLAY "CAWRMTCH W2 ONLY " C4
           DISPLAY "CAWRMTCH DISCREP " C5
           STOP RUN.
      *
      *    THREE WAY MERGE.  THE 941 SIDE IS SUMMARISED BY EIN AND
      *    YEAR BEFORE COMPARISON, SO THE MODULE SIDE ADVANCES A
      *    WHOLE CONTROL GROUP AT A TIME.
      *
       2000-MATCH.
           EVALUATE TRUE
               WHEN MKEY < WKEY
                   PERFORM 3000-GRP
                   PERFORM 4100-941ONLY
               WHEN MKEY > WKEY
                   PERFORM 4200-W2ONLY
                   PERFORM 8200-RDW2
               WHEN OTHER
                   PERFORM 3000-GRP
                   PERFORM 4000-CMP
                   PERFORM 8200-RDW2
           END-EVALUATE.
      *
      *    CONTROL BREAK.  ACCUMULATE EVERY MFT 01 MODULE CARRYING
      *    THE CURRENT EIN AND YEAR.
      *
       3000-GRP.
           MOVE MKEY TO HKEY
           MOVE ZERO TO LIAB
           MOVE ZERO TO NQTR
           PERFORM UNTIL MEOF = "Y" OR MKEY NOT = HKEY
               ADD BMF-ASSD TO LIAB
               ADD 1 TO NQTR
               PERFORM 8100-RDMOD
           END-PERFORM
           ADD 1 TO C1.
       4000-CMP.
           COMPUTE DIFF = HW-WHLD - LIAB
           COMPUTE TOLR = LIAB * 0.01
           IF TOLR < 100
               MOVE 100 TO TOLR
           END-IF
           MOVE W2-EIN TO CR-EIN
           MOVE HKEY(10:4) TO CR-YR
           MOVE HW-WHLD TO CR-W2
           MOVE LIAB TO CR-941
           MOVE DIFF TO CR-DIFF
           IF FUNCTION ABS(DIFF) NOT > TOLR
               ADD 1 TO C3
               MOVE "C001" TO CR-COD
               MOVE "IN BALANCE" TO CR-TXT
           ELSE
               ADD 1 TO C5
               IF DIFF > ZERO
                   MOVE "C002" TO CR-COD
                   MOVE "W2 EXCEEDS 941 LIABILITY" TO CR-TXT
               ELSE
                   MOVE "C003" TO CR-COD
                   MOVE "941 EXCEEDS W2 REPORTED" TO CR-TXT
               END-IF
           END-IF
           WRITE CWRPT-REC FROM CRPT.
       4100-941ONLY.
           ADD 1 TO C5
           MOVE HKEY(1:9) TO CR-EIN
           MOVE HKEY(10:4) TO CR-YR
           MOVE "C004" TO CR-COD
           MOVE "NO W2 DATA FROM SSA" TO CR-TXT
           MOVE ZERO TO CR-W2
           MOVE LIAB TO CR-941
           COMPUTE DIFF = ZERO - LIAB
           MOVE DIFF TO CR-DIFF
           WRITE CWRPT-REC FROM CRPT.
       4200-W2ONLY.
           ADD 1 TO C4
           MOVE W2-EIN TO CR-EIN
           MOVE W2-YR TO CR-YR
           MOVE "C005" TO CR-COD
           MOVE "W2 FILED - NO 941 MODULE" TO CR-TXT
           MOVE HW-WHLD TO CR-W2
           MOVE ZERO TO CR-941
           MOVE HW-WHLD TO CR-DIFF
           WRITE CWRPT-REC FROM CRPT.
      *
      *    ONLY MFT 01 PARTICIPATES IN CAWR.  OTHER MFTS ARE SKIPPED
      *    ON THE READ SO THEY NEVER REACH THE MERGE.
      *
       8100-RDMOD.
           MOVE "N" TO FS1
           PERFORM UNTIL MEOF = "Y"
               READ MODIN
                   AT END
                       MOVE "Y" TO MEOF
                       MOVE HIGH-VALUES TO MKEY
                   NOT AT END
                       IF BMF-MFT = 01
                           MOVE BMF-EIN TO MKEY(1:9)
                           MOVE BMF-TXPD(1:4) TO MKEY(10:4)
                           MOVE "Y" TO FS1
                       END-IF
               END-READ
               IF FS1 = "Y"
                   EXIT PERFORM
               END-IF
           END-PERFORM.
       8200-RDW2.
           READ W2IN INTO W2REC
               AT END
                   MOVE "Y" TO WEOF
                   MOVE HIGH-VALUES TO WKEY
               NOT AT END
                   ADD 1 TO C2
                   MOVE W2-EIN TO WKEY(1:9)
                   MOVE W2-YR TO WKEY(10:4)
                   MOVE W2-WAGE TO HW-WAGE
                   MOVE W2-WHLD TO HW-WHLD
                   MOVE W2-DOC TO HW-DOC
           END-READ.
