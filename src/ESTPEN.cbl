       IDENTIFICATION DIVISION.
       PROGRAM-ID. ESTPEN.
      *****************************************************************
      *    CORPORATE ESTIMATED TAX PENALTY - IRC 6655                 *
      *    STEP 060.  FOUR REQUIRED INSTALLMENTS AT 25 PCT OF THE     *
      *    REQUIRED ANNUAL PAYMENT.  MFT 02 ONLY.                     *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODPEN.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT MODOT  ASSIGN TO "data/MODEST.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT ESRPT  ASSIGN TO "data/ESTPEN.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  ESRPT.
       01  ESRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  E1                      PIC 9(6) VALUE ZERO.
       01  E2                      PIC 9(6) VALUE ZERO.
       01  E3                      PIC 9(6) VALUE ZERO.
       01  RAP                     PIC S9(11)V99 COMP-3.
       01  RQI                     PIC S9(11)V99 COMP-3.
       01  PDI                     PIC S9(11)V99 COMP-3.
       01  UND                     PIC S9(11)V99 COMP-3.
       01  ACC                     PIC S9(9)V99 COMP-3.
       01  QAMT                    PIC S9(9)V99 COMP-3.
       01  QI                      PIC S9(4) COMP.
       01  QDAYS                   PIC S9(4) COMP.
       01  QRATE                   PIC S9(1)V9(4) COMP-3.
       01  ERPT.
           05  FILLER              PIC X(06) VALUE "ESTPEN".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ER-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  ER-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ER-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ER-TXT              PIC X(24).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  ER-Q                PIC 9(01).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  ER-UND              PIC ZZZZZZZ9.99.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  ER-AMT              PIC ZZZZZZ9.99.
           05  FILLER              PIC X(35) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN OUTPUT MODOT ESRPT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           CLOSE MODIN MODOT ESRPT
           DISPLAY "ESTPEN  READ    " E1
           DISPLAY "ESTPEN  WRITTEN " E2
           DISPLAY "ESTPEN  ASSESSED" E3
           STOP RUN.
       2000-PROC.
           READ MODIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO E1
                   IF BMF-MFT = 02
                       PERFORM 2100-EST THRU 2100-X
                   END-IF
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO E2
           END-READ.
      *
      *    REQUIRED ANNUAL PAYMENT IS THE LESSER OF 100 PCT OF THE
      *    TAX SHOWN OR 100 PCT OF THE PRIOR YEAR.  PRIOR YEAR IS NOT
      *    CARRIED ON THE MODULE SO THE CURRENT YEAR IS USED.
      *
       2100-EST.
           MOVE ZERO TO ACC
           MOVE BMF-ASSD TO RAP
           IF RAP < 500
               GO TO 2100-X
           END-IF
           COMPUTE RQI = RAP * 0.25
           COMPUTE PDI = BMF-DEP * 0.25
           COMPUTE UND = RQI - PDI
           IF UND NOT > ZERO
               GO TO 2100-X
           END-IF
           MOVE 0.0008 TO QRATE
           PERFORM VARYING QI FROM 1 BY 1 UNTIL QI > 4
               EVALUATE QI
                   WHEN 1
                       MOVE 275 TO QDAYS
                   WHEN 2
                       MOVE 183 TO QDAYS
                   WHEN 3
                       MOVE 92 TO QDAYS
                   WHEN OTHER
                       MOVE 30 TO QDAYS
               END-EVALUATE
               COMPUTE QAMT ROUNDED = UND * QRATE * QDAYS / 30
               ADD QAMT TO ACC
               MOVE BMF-EIN TO ER-EIN
               MOVE BMF-TXPD TO ER-TXPD
               MOVE "E601" TO ER-COD
               MOVE "INSTALLMENT SHORTFALL" TO ER-TXT
               MOVE QI TO ER-Q
               MOVE UND TO ER-UND
               MOVE QAMT TO ER-AMT
               WRITE ESRPT-REC FROM ERPT
           END-PERFORM
           ADD ACC TO BMF-PFTP
           ADD 1 TO E3.
       2100-X.
           EXIT.
