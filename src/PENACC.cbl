       IDENTIFICATION DIVISION.
       PROGRAM-ID. PENACC.
      *****************************************************************
      *    PENALTY ACCUMULATION.  COBOL SHIM FOR THE HLASM ROUTINE    *
      *    OF THE SAME NAME - SEE SRC/ASM/PENACC.ASM.  THE ASSEMBLER  *
      *    DOES ZAP/MP/SRP AGAINST THE SAME PACKED FIELDS.            *
      *****************************************************************
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  PZ                      PIC S9(11)V9(6) COMP-3.
       LINKAGE SECTION.
       01  PA-PARM.
           05  PA-BAS              PIC S9(11)V99 COMP-3.
           05  PA-RT               PIC S9(01)V9(04) COMP-3.
           05  PA-ACC              PIC S9(09)V99 COMP-3.
           05  PA-AMT              PIC S9(09)V99 COMP-3.
           05  PA-RC               PIC X(01).
           05  PA-RSV              PIC X(09).
       PROCEDURE DIVISION USING PA-PARM.
       0000-ENT.
           MOVE "0" TO PA-RC
           IF PA-BAS < ZERO
               MOVE "8" TO PA-RC
               MOVE ZERO TO PA-AMT
               GOBACK
           END-IF
           COMPUTE PZ = PA-BAS * PA-RT
           COMPUTE PA-AMT ROUNDED = PZ
           ADD PA-AMT TO PA-ACC
           GOBACK.
       END PROGRAM PENACC.
