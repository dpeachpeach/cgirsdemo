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
       01  WRAP                     PIC S9(11)V99 COMP-3.
       01  WRQI                     PIC S9(11)V99 COMP-3.
       01  WPDI                     PIC S9(11)V99 COMP-3.
       01  WUND                     PIC S9(11)V99 COMP-3.
       01  WACC                     PIC S9(9)V99 COMP-3.
       01  WQAM                    PIC S9(9)V99 COMP-3.
       01  QI                      PIC S9(4) COMP.
       01  WQDY                   PIC S9(4) COMP.
       01  WQRT                   PIC S9(1)V9(4) COMP-3.
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
       2100-EST.
           MOVE ZERO TO WACC
           MOVE BMF-ASSD TO WRAP
           IF WRAP < 500
               GO TO 2100-X
           END-IF
           COMPUTE WRQI = WRAP * 0.25
           COMPUTE WPDI = BMF-DEP * 0.25
           COMPUTE WUND = WRQI - WPDI
           IF WUND NOT > ZERO
               GO TO 2100-X
           END-IF
           MOVE 0.0008 TO WQRT
           PERFORM VARYING QI FROM 1 BY 1 UNTIL QI > 4
               EVALUATE QI
                   WHEN 1
                       MOVE 275 TO WQDY
                   WHEN 2
                       MOVE 183 TO WQDY
                   WHEN 3
                       MOVE 92 TO WQDY
                   WHEN OTHER
                       MOVE 30 TO WQDY
               END-EVALUATE
               COMPUTE WQAM ROUNDED = WUND * WQRT * WQDY / 30
               ADD WQAM TO WACC
               MOVE BMF-EIN TO ER-EIN
               MOVE BMF-TXPD TO ER-TXPD
               MOVE "E601" TO ER-COD
               MOVE "INSTALLMENT SHORTFALL" TO ER-TXT
               MOVE QI TO ER-Q
               MOVE WUND TO ER-UND
               MOVE WQAM TO ER-AMT
               WRITE ESRPT-REC FROM ERPT
           END-PERFORM
           ADD WACC TO BMF-PFTP
           ADD 1 TO E3.
       2100-X.
           EXIT.
