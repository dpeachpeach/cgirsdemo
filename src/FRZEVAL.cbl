       IDENTIFICATION DIVISION.
       PROGRAM-ID. FRZEVAL.
      *****************************************************************
      *    FREEZE CONDITION EVALUATION - IRM 21.5.6                   *
      *    STEP 070.  DETERMINES REFUND AND OFFSET ELIGIBILITY FROM   *
      *    THE FREEZE POSITIONS CARRIED ON THE MODULE.                *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODEST.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT MODOT  ASSIGN TO "data/MODFRZ.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT FZRPT  ASSIGN TO "data/FRZEVAL.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  FZRPT.
       01  FZRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  V1                      PIC 9(6) VALUE ZERO.
       01  V2                      PIC 9(6) VALUE ZERO.
       01  V3                      PIC 9(6) VALUE ZERO.
       01  V4                      PIC 9(6) VALUE ZERO.
       01  BAL                     PIC S9(11)V99 COMP-3.
       01  RFSW                    PIC X.
       01  OFSW                    PIC X.
       01  FZCT                    PIC 9(2).
       01  ZRPT.
           05  FILLER              PIC X(07) VALUE "FRZEVAL".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ZR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  ZR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  ZR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ZR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ZR-TXT              PIC X(30).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ZR-FRZ              PIC X(08).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ZR-BAL              PIC ZZZZZZZZ9.99-.
           05  FILLER              PIC X(20) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN OUTPUT MODOT FZRPT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           CLOSE MODIN MODOT FZRPT
           DISPLAY "FRZEVAL READ    " V1
           DISPLAY "FRZEVAL WRITTEN " V2
           DISPLAY "FRZEVAL RFND SUP" V3
           DISPLAY "FRZEVAL OFST SUP" V4
           STOP RUN.
       2000-PROC.
           READ MODIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO V1
                   PERFORM 2100-FRZ
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO V2
           END-READ.
       2100-FRZ.
           MOVE "Y" TO RFSW
           MOVE "Y" TO OFSW
           MOVE ZERO TO FZCT
           COMPUTE BAL = BMF-ASSD + BMF-PFTD + BMF-PFTF + BMF-PFTP
               - BMF-DEP - BMF-CRD
      *
      *    -A  DUPLICATE FILING.  REFUND HELD PENDING RESOLUTION.
      *
           IF BMF-FRZ-A = "A"
               MOVE "N" TO RFSW
               ADD 1 TO FZCT
           END-IF
      *
      *    -L  EXAMINATION OPEN.  REFUND AND OFFSET BOTH HELD.
      *
           IF BMF-FRZ-L = "L"
               MOVE "N" TO RFSW
               MOVE "N" TO OFSW
               ADD 1 TO FZCT
           END-IF
      *
      *    -V  BANKRUPTCY.  AUTOMATIC STAY BARS OFFSET.
      *
           IF BMF-FRZ-V = "V"
               MOVE "N" TO OFSW
               ADD 1 TO FZCT
           END-IF
      *
      *    -S  DISASTER.  COMPLIANCE ACTIVITY SUSPENDED.
      *
           IF BMF-FRZ-S = "S"
               MOVE "N" TO RFSW
               ADD 1 TO FZCT
           END-IF
      *
      *    -Z  CRIMINAL INVESTIGATION CONTROL.
      *
           IF BMF-FRZ-Z = "Z"
               MOVE "N" TO RFSW
               MOVE "N" TO OFSW
               ADD 1 TO FZCT
           END-IF
           IF RFSW = "N"
               ADD 1 TO V3
               MOVE "R" TO BMF-FRZ-R
           END-IF
           IF OFSW = "N"
               ADD 1 TO V4
               MOVE "O" TO BMF-FRZ-O
           END-IF
           IF FZCT > ZERO
               MOVE BMF-EIN TO ZR-EIN
               MOVE BMF-MFT TO ZR-MFT
               MOVE BMF-TXPD TO ZR-TXPD
               MOVE "Z701" TO ZR-COD
               IF RFSW = "N" AND OFSW = "N"
                   MOVE "REFUND AND OFFSET SUPPRESSED" TO ZR-TXT
               ELSE
                   IF RFSW = "N"
                       MOVE "REFUND SUPPRESSED" TO ZR-TXT
                   ELSE
                       MOVE "OFFSET SUPPRESSED" TO ZR-TXT
                   END-IF
               END-IF
               MOVE BMF-FRZ TO ZR-FRZ
               MOVE BAL TO ZR-BAL
               WRITE FZRPT-REC FROM ZRPT
           END-IF.
