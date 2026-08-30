       IDENTIFICATION DIVISION.
       PROGRAM-ID. NAMCTL.
      *****************************************************************
      *    NAME CONTROL DERIVATION.  COBOL SHIM FOR THE HLASM         *
      *    ROUTINE OF THE SAME NAME - SEE SRC/ASM/NAMCTL.ASM.         *
      *    PARM AREA IS MAPPED BY DISPLACEMENT, NOT BY NAME.          *
      *****************************************************************
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  N1                      PIC S9(4) COMP.
       01  N2                      PIC S9(4) COMP.
       01  N3                      PIC S9(4) COMP.
       01  WK01                    PIC X(35).
       01  WK02                    PIC X(35).
       01  WK03                    PIC X(01).
       01  WK04                    PIC S9(4) COMP.
       01  WK05                    PIC X(01).
       LINKAGE SECTION.
       01  NC-PARM.
           05  NCP-NAME            PIC X(35).
           05  NCP-NCTL            PIC X(04).
           05  NCP-RC              PIC X(01).
           05  NCP-RSV             PIC X(08).
       PROCEDURE DIVISION USING NC-PARM.
       0000-ENT.
           MOVE "0" TO NCP-RC
           MOVE SPACES TO NCP-NCTL
           MOVE FUNCTION UPPER-CASE(NCP-NAME) TO WK01
           PERFORM 1000-CNTWD
           PERFORM 2000-DROPTHE
           PERFORM 3000-SQUEEZE
           IF WK02 = SPACES
               MOVE "8" TO NCP-RC
           ELSE
               MOVE WK02(1:4) TO NCP-NCTL
           END-IF
           GOBACK.
       1000-CNTWD.
           MOVE ZERO TO WK04
           MOVE " " TO WK05
           PERFORM VARYING N1 FROM 1 BY 1 UNTIL N1 > 35
               MOVE WK01(N1:1) TO WK03
               IF WK03 NOT = " " AND WK05 = " "
                   ADD 1 TO WK04
               END-IF
               MOVE WK03 TO WK05
           END-PERFORM.
       2000-DROPTHE.
           IF WK01(1:4) = "THE "
               MOVE WK01(5:31) TO WK01
           END-IF.
       3000-SQUEEZE.
           MOVE SPACES TO WK02
           MOVE ZERO TO N2
           PERFORM VARYING N1 FROM 1 BY 1 UNTIL N1 > 35
               MOVE WK01(N1:1) TO WK03
               IF (WK03 NOT = " ") AND (WK03 NOT = ",")
                  AND (WK03 NOT = ".") AND (WK03 NOT = "'")
                  AND (WK03 NOT = "-")
                   ADD 1 TO N2
                   MOVE WK03 TO WK02(N2:1)
               END-IF
           END-PERFORM.
       END PROGRAM NAMCTL.
