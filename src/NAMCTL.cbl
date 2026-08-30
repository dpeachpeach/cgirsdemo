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
       01  WKNM                    PIC X(35).
       01  WKSQ                    PIC X(35).
       01  WKCH                    PIC X(01).
       01  WKWD                    PIC S9(4) COMP.
       01  WKPR                    PIC X(01).
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
           MOVE FUNCTION UPPER-CASE(NCP-NAME) TO WKNM
           PERFORM 1000-CNTWD
           PERFORM 2000-DROPTHE
           PERFORM 3000-SQUEEZE
           IF WKSQ = SPACES
               MOVE "8" TO NCP-RC
           ELSE
               MOVE WKSQ(1:4) TO NCP-NCTL
           END-IF
           GOBACK.
      *
      *    COUNT BLANK-DELIMITED WORDS.
      *
       1000-CNTWD.
           MOVE ZERO TO WKWD
           MOVE " " TO WKPR
           PERFORM VARYING N1 FROM 1 BY 1 UNTIL N1 > 35
               MOVE WKNM(N1:1) TO WKCH
               IF WKCH NOT = " " AND WKPR = " "
                   ADD 1 TO WKWD
               END-IF
               MOVE WKCH TO WKPR
           END-PERFORM.
      *
      *    IRM 3.13.2.3.1(3)(4). THE WORD "THE" IS BRACKETED OUT WHEN
      *    MORE THAN ONE WORD FOLLOWS IT.  WHEN ONLY ONE WORD FOLLOWS
      *    IT THE "THE" IS RETAINED.
      *
       2000-DROPTHE.
           IF WKNM(1:4) = "THE " AND WKWD > 2
               MOVE WKNM(5:31) TO WKNM
           END-IF.
      *
      *    REMOVE EMBEDDED BLANKS AND PUNCTUATION.
      *
       3000-SQUEEZE.
           MOVE SPACES TO WKSQ
           MOVE ZERO TO N2
           PERFORM VARYING N1 FROM 1 BY 1 UNTIL N1 > 35
               MOVE WKNM(N1:1) TO WKCH
               IF (WKCH NOT = " ") AND (WKCH NOT = ",")
                  AND (WKCH NOT = ".") AND (WKCH NOT = "'")
                  AND (WKCH NOT = "-")
                   ADD 1 TO N2
                   MOVE WKCH TO WKSQ(N2:1)
               END-IF
           END-PERFORM.
       END PROGRAM NAMCTL.
