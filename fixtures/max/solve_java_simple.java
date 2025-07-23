import java.util.Scanner;

public class solve_java_simple {
        public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int count = scanner.nextInt();
        int max = 0;
        for (int i = 0; i < count; i++) {
            int number = scanner.nextInt();
            max = Math.max(max, number);
        }
        System.out.println(max);
    }
}
