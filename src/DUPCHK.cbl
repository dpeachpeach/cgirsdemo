       IDENTIFICATION DIVISION.
       PROGRAM-ID. DUPCHK.
      *****************************************************************
      *    DUPLICATE FILING CONDITION - TC 150/976/977                *
      *    SETS -A FREEZE.  APPLIES TC 560 ASED CORRECTION.           *
      *    STEP 020.  INPUT MUST BE SORTED EIN/MFT/TXPD.              *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/BMFMOD.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT TRNIN  ASSIGN TO "data/TRANIN.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT MODOT  ASSIGN TO "data/MODDUP.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS3.
           SELECT DUPRPT ASSIGN TO "data/DUPCHK.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  TRNIN
           RECORD CONTAINS 80 CHARACTERS.
       COPY TRANREC.
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  DUPRPT.
       01  DUPRPT-REC              PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  FS3                     PIC XX VALUE "00".
       01  MEOF                    PIC X VALUE "N".
       01  TEOF                    PIC X VALUE "N".
       01  R1                      PIC 9(6) VALUE ZERO.
       01  R2                      PIC 9(6) VALUE ZERO.
       01  R3                      PIC 9(6) VALUE ZERO.
       01  R4                      PIC 9(6) VALUE ZERO.
       01  C50                     PIC 9(3).
       01  C76                     PIC 9(3).
       01  C77                     PIC 9(3).
       01  C60                     PIC 9(3).
       01  D60                     PIC 9(7).
       01  D76                     PIC 9(7).
       01  MKEY                    PIC X(17).
       01  TKEY                    PIC X(17).
       01  DUPSW                   PIC X.
       01  W-ASED                  PIC 9(7).
       01  DRPT.
           05  FILLER              PIC X(06) VALUE "DUPCHK".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  DR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  DR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  DR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  DR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  DR-TXT              PIC X(38).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  DR-A                PIC 9(03).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  DR-B                PIC 9(03).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  DR-C                PIC 9(07).
           05  FILLER              PIC X(30) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-INIT
           PERFORM 2000-DRIVE UNTIL MEOF = "Y"
           PERFORM 9000-EOJ
           STOP RUN.
       1000-INIT.
           OPEN INPUT MODIN TRNIN OUTPUT MODOT DUPRPT
           PERFORM 8100-RDTRN.
       2000-DRIVE.
           READ MODIN
               AT END
                   MOVE "Y" TO MEOF
               NOT AT END
                   ADD 1 TO R1
                   PERFORM 2100-MOD
           END-READ.
       2100-MOD.
           MOVE BMF-KEY TO MKEY
           MOVE ZERO TO C50
           MOVE ZERO TO C76
           MOVE ZERO TO C77
           MOVE ZERO TO C60
           MOVE ZERO TO D60
           MOVE ZERO TO D76
           MOVE "N" TO DUPSW
           PERFORM 2200-SKIP
           PERFORM 2300-GATHER
           PERFORM 2400-EVAL
           WRITE MODOT-REC FROM BMF-MOD-REC
           ADD 1 TO R2.
      *
      *    DISCARD TRANSACTIONS THAT SORT LOW - NO MODULE ON FILE.
      *
       2200-SKIP.
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT < MKEY
               PERFORM 8100-RDTRN
           END-PERFORM.
      *
      *    ACCUMULATE THE TRANSACTIONS BELONGING TO THIS MODULE.
      *
       2300-GATHER.
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT = MKEY
               EVALUATE TRN-TC
                   WHEN 150
                       ADD 1 TO C50
                   WHEN 976
                       ADD 1 TO C76
                       MOVE TRN-DT TO D76
                   WHEN 977
                       ADD 1 TO C77
                   WHEN 560
                       ADD 1 TO C60
                       MOVE TRN-DT TO D60
               END-EVALUATE
               ADD 1 TO BMF-TCCNT
               PERFORM 8100-RDTRN
           END-PERFORM.
      *
      *    IRM 21.7.9.  A TC 976 OR TC 977 POSTING TO A MODULE THAT
      *    ALREADY CARRIES A TC 150 IS A DUPLICATE FILING CONDITION
      *    AND SETS THE -A FREEZE.
      *
       2400-EVAL.
           IF C50 > ZERO AND (C76 > ZERO OR C77 > ZERO)
               MOVE "Y" TO DUPSW
           END-IF
           IF C50 > 1
               MOVE "Y" TO DUPSW
           END-IF
           IF DUPSW = "Y"
               MOVE "A" TO BMF-FRZ-A
               ADD 1 TO R3
               MOVE BMF-EIN TO DR-EIN
               MOVE BMF-MFT TO DR-MFT
               MOVE BMF-TXPD TO DR-TXPD
               MOVE "D201" TO DR-COD
               MOVE "DUP FILING - A FREEZE SET" TO DR-TXT
               MOVE C76 TO DR-A
               MOVE C77 TO DR-B
               MOVE D76 TO DR-C
               WRITE DUPRPT-REC FROM DRPT
           END-IF
           PERFORM 2500-ASED.
      *
      *    TC 560 CARRIES A CORRECTED ASED.  IT REPLACES THE MODULE
      *    ASED ONLY WHEN IT EXTENDS THE PERIOD.
      *
       2500-ASED.
           IF C60 > ZERO
               MOVE BMF-ASED TO W-ASED
               IF D60 > W-ASED
                   MOVE D60 TO BMF-ASED
                   ADD 1 TO R4
                   MOVE BMF-EIN TO DR-EIN
                   MOVE BMF-MFT TO DR-MFT
                   MOVE BMF-TXPD TO DR-TXPD
                   MOVE "D202" TO DR-COD
                   MOVE "TC 560 ASED CORRECTION APPLIED" TO DR-TXT
                   MOVE ZERO TO DR-A
                   MOVE ZERO TO DR-B
                   MOVE D60 TO DR-C
                   WRITE DUPRPT-REC FROM DRPT
               END-IF
           END-IF.
       8100-RDTRN.
           READ TRNIN
               AT END
                   MOVE "Y" TO TEOF
                   MOVE HIGH-VALUES TO TKEY
               NOT AT END
                   MOVE TRN-EIN  TO TKEY(1:9)
                   MOVE TRN-MFT  TO TKEY(10:2)
                   MOVE TRN-TXPD TO TKEY(12:6)
           END-READ.
       9000-EOJ.
           CLOSE MODIN TRNIN MODOT DUPRPT
           DISPLAY "DUPCHK  READ    " R1
           DISPLAY "DUPCHK  WRITTEN " R2
           DISPLAY "DUPCHK  A FREEZE" R3
           DISPLAY "DUPCHK  ASED COR" R4.
